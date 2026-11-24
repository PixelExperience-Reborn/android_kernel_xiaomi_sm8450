// SPDX-License-Identifier: GPL-2.0-only
/*
 * Copyright (c) 2021, The Linux Foundation. All rights reserved.
 */

#define pr_fmt(fmt) "%s:%s " fmt, KBUILD_MODNAME, __func__

#include <linux/devfreq.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/pm_opp.h>
#include <linux/pm_qos.h>
#include <linux/slab.h>
#include <linux/thermal.h>
#include <linux/workqueue.h>

#define MAX_RETRY_CNT 20
#define RETRY_DELAY msecs_to_jiffies(1000)
#define DEVFREQ_CDEV_NAME "gpu"
#define DEVFREQ_CDEV "qcom-devfreq-cdev"

struct devfreq_cdev_device {
	struct device_node *np;
	struct devfreq *devfreq;
	struct device *dev;
	unsigned long *freq_table;
	int cur_state;
	int max_state;
	int retry_cnt;
	struct dev_pm_qos_request qos_max_freq_req;
	struct delayed_work register_work;
	struct thermal_cooling_device *cdev;
};

static int devfreq_cdev_set_state(struct thermal_cooling_device *cdev,
					unsigned long state)
{
	struct devfreq_cdev_device *cdev_data = cdev->devdata;
	int ret = 0;
	unsigned long freq;

	if (state > cdev_data->max_state)
		return -EINVAL;
	if (state == cdev_data->cur_state)
		return 0;
	freq = cdev_data->freq_table[state];
	pr_debug("cdev:%s Limit:%lu\n", cdev->type, freq);
	ret = dev_pm_qos_update_request(&cdev_data->qos_max_freq_req, freq);
	if (ret < 0) {
		pr_err("Error placing qos request:%lu. cdev:%s err:%d\n",
				freq, cdev->type, ret);
		return ret;
	}
	cdev_data->cur_state = state;

	return 0;
}

static int devfreq_cdev_get_state(struct thermal_cooling_device *cdev,
					unsigned long *state)
{
	struct devfreq_cdev_device *cdev_data = cdev->devdata;

	*state = cdev_data->cur_state;
	return 0;
}

static int devfreq_cdev_get_max_state(struct thermal_cooling_device *cdev,
					unsigned long *state)
{
	struct devfreq_cdev_device *cdev_data = cdev->devdata;

	*state = cdev_data->max_state;
	return 0;
}

static struct thermal_cooling_device_ops devfreq_cdev_ops = {
	.set_cur_state = devfreq_cdev_set_state,
	.get_cur_state = devfreq_cdev_get_state,
	.get_max_state = devfreq_cdev_get_max_state,
};

static void devfreq_cdev_work(struct work_struct *work)
{
	struct devfreq_cdev_device *cdev_data = container_of(work,
						struct devfreq_cdev_device,
						register_work.work);
	struct devfreq *df;
	struct dev_pm_opp *opp;
	unsigned long freq = ULONG_MAX;
	unsigned long *freq_table;
	int ret, freq_ct, i;

	df = devfreq_get_devfreq_by_node(cdev_data->np);
	if (IS_ERR(df)) {
		ret = PTR_ERR(df);
		pr_debug("Devfreq not available: %d\n", ret);
		goto retry;
	}

	cdev_data->dev = df->dev.parent;
	cdev_data->devfreq = df;
	freq_ct = dev_pm_opp_get_opp_count(cdev_data->dev);
	if (freq_ct <= 0) {
		ret = freq_ct < 0 ? freq_ct : -EPROBE_DEFER;
		pr_debug("Devfreq OPP table not ready: %d\n", ret);
		goto retry;
	}

	freq_table = kcalloc(freq_ct, sizeof(*freq_table), GFP_KERNEL);
	if (!freq_table) {
		pr_err("Failed to allocate devfreq OPP table\n");
		return;
	}

	for (i = 0, freq = ULONG_MAX; i < freq_ct; i++, freq--) {
		opp = dev_pm_opp_find_freq_floor(cdev_data->dev, &freq);
		if (IS_ERR(opp)) {
			ret = PTR_ERR(opp);
			pr_err("Failed to read GPU OPP %d: %d\n", i, ret);
			goto free_table;
		}
		dev_pm_opp_put(opp);

		freq_table[i] = DIV_ROUND_UP(freq, 1000); /* Hz to kHz */
		pr_debug("%d. freq table:%lu\n", i, freq_table[i]);
	}
	cdev_data->max_state = freq_ct - 1;
	cdev_data->freq_table = freq_table;
	ret = dev_pm_qos_add_request(cdev_data->dev,
					&cdev_data->qos_max_freq_req,
					DEV_PM_QOS_MAX_FREQUENCY,
					PM_QOS_MAX_FREQUENCY_DEFAULT_VALUE);
	if (ret < 0) {
		pr_err("Failed to add GPU frequency QoS: %d\n", ret);
		goto free_table;
	}

	cdev_data->cdev = thermal_cooling_device_register(DEVFREQ_CDEV_NAME,
						cdev_data, &devfreq_cdev_ops);
	if (IS_ERR(cdev_data->cdev)) {
		ret = PTR_ERR(cdev_data->cdev);
		pr_err("GPU cooling device registration failed: %d\n", ret);
		cdev_data->cdev = NULL;
		dev_pm_qos_remove_request(&cdev_data->qos_max_freq_req);
		goto free_table;
	}
	return;

free_table:
	kfree(freq_table);
	cdev_data->freq_table = NULL;
	return;

retry:
	if (--cdev_data->retry_cnt > 0)
		queue_delayed_work(system_highpri_wq, &cdev_data->register_work,
				RETRY_DELAY);
	else
		pr_err("GPU cooling registration unavailable after retries: %d\n",
			ret);
}

static int devfreq_cdev_probe(struct platform_device *pdev)
{
	struct devfreq_cdev_device *cdev_data;
	struct device *dev = &pdev->dev;

	cdev_data = devm_kzalloc(dev, sizeof(*cdev_data), GFP_KERNEL);
	if (!cdev_data)
		return -ENOMEM;

	cdev_data->np = of_parse_phandle(dev->of_node, "qcom,devfreq", 0);
	if (!cdev_data->np)
		return -EINVAL;

	cdev_data->retry_cnt = MAX_RETRY_CNT;
	platform_set_drvdata(pdev, cdev_data);

	INIT_DEFERRABLE_WORK(&cdev_data->register_work, devfreq_cdev_work);
	queue_delayed_work(system_highpri_wq, &cdev_data->register_work, 0);
	return 0;
}

static int devfreq_cdev_remove(struct platform_device *pdev)
{
	struct devfreq_cdev_device *cdev_data = platform_get_drvdata(pdev);

	cancel_delayed_work_sync(&cdev_data->register_work);
	if (cdev_data->cdev) {
		thermal_cooling_device_unregister(cdev_data->cdev);
		dev_pm_qos_remove_request(&cdev_data->qos_max_freq_req);
		kfree(cdev_data->freq_table);
		cdev_data->cdev = NULL;
	}
	of_node_put(cdev_data->np);
	return 0;
}

static const struct of_device_id devfreq_cdev_match[] = {
	{.compatible = "qcom,devfreq-cdev"},
	{}
};

static struct platform_driver devfreq_cdev_driver = {
	.probe          = devfreq_cdev_probe,
	.remove         = devfreq_cdev_remove,
	.driver         = {
		.name   = DEVFREQ_CDEV,
		.of_match_table = devfreq_cdev_match,
	},
};

static int __init devfreq_cdev_init(void)
{
	return platform_driver_register(&devfreq_cdev_driver);
}
module_init(devfreq_cdev_init);

static void __exit devfreq_cdev_exit(void)
{
	platform_driver_unregister(&devfreq_cdev_driver);
}
module_exit(devfreq_cdev_exit);

MODULE_DESCRIPTION("Qualcomm Technologies, Inc. devfreq cooling device driver");
MODULE_LICENSE("GPL v2");
