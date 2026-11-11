// SPDX-License-Identifier: GPL-2.0-only
/*
 * Copyright (c) 2021, The Linux Foundation. All rights reserved.
 */

#define pr_fmt(fmt) "%s:%s " fmt, KBUILD_MODNAME, __func__

#include <linux/cpu.h>
#include <linux/cpufreq.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/notifier.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/pm_qos.h>
#include <linux/slab.h>
#include <linux/sort.h>
#include <linux/thermal.h>
#include <linux/workqueue.h>

#define CPUFREQ_CDEV_NAME "cpu%d"
#define CPUFREQ_CDEV "qcom-cpufreq-cdev"

struct cpufreq_cdev_device {
	struct list_head node;
	struct thermal_cooling_device *cdev;
	struct mutex state_lock;
	int cpu;
	unsigned long cur_state;
	unsigned long max_state;
	unsigned int *freq_table;
	struct freq_qos_request qos_max_freq_req;
	char cdev_name[THERMAL_NAME_LENGTH];
	struct cpufreq_policy *policy;
	struct work_struct reg_work;
};

static DEFINE_MUTEX(qti_cpufreq_cdev_lock);
static LIST_HEAD(qti_cpufreq_cdev_list);
static enum cpuhp_state cpu_hp_online;
static struct device *cpufreq_cdev_owner;
static bool cpufreq_policy_notifier_registered;

static unsigned int state_to_cpufreq(struct cpufreq_cdev_device *cdev_data,
				    unsigned long state)
{
	return cdev_data->freq_table[state];
}

static int cpufreq_cdev_set_state(struct thermal_cooling_device *cdev,
				 unsigned long state)
{
	struct cpufreq_cdev_device *cdev_data = cdev->devdata;
	unsigned int freq;
	int ret = 0;

	if (state > cdev_data->max_state)
		return -EINVAL;

	mutex_lock(&cdev_data->state_lock);
	if (state == cdev_data->cur_state)
		goto out_unlock;

	if (!freq_qos_request_active(&cdev_data->qos_max_freq_req)) {
		ret = -ENODEV;
		goto out_unlock;
	}

	freq = state_to_cpufreq(cdev_data, state);
	pr_debug("cdev:%s Limit:%u\n", cdev->type, freq);
	ret = freq_qos_update_request(&cdev_data->qos_max_freq_req, freq);
	if (ret < 0) {
		pr_err("Error placing qos request:%u. cdev:%s err:%d\n",
		       freq, cdev->type, ret);
		goto out_unlock;
	}
	cdev_data->cur_state = state;
	ret = 0;

out_unlock:
	mutex_unlock(&cdev_data->state_lock);
	return ret;
}

static int cpufreq_cdev_get_state(struct thermal_cooling_device *cdev,
				 unsigned long *state)
{
	struct cpufreq_cdev_device *cdev_data = cdev->devdata;

	mutex_lock(&cdev_data->state_lock);
	*state = cdev_data->cur_state;
	mutex_unlock(&cdev_data->state_lock);
	return 0;
}

static int cpufreq_cdev_get_max_state(struct thermal_cooling_device *cdev,
				     unsigned long *state)
{
	struct cpufreq_cdev_device *cdev_data = cdev->devdata;

	*state = cdev_data->max_state;
	return 0;
}

static struct thermal_cooling_device_ops cpufreq_cdev_ops = {
	.set_cur_state = cpufreq_cdev_set_state,
	.get_cur_state = cpufreq_cdev_get_state,
	.get_max_state = cpufreq_cdev_get_max_state,
};

static int cpufreq_desc_cmp(const void *a, const void *b)
{
	unsigned int left = *(const unsigned int *)a;
	unsigned int right = *(const unsigned int *)b;

	return (left < right) - (left > right);
}

static void cpufreq_cdev_register(struct work_struct *work)
{
	struct cpufreq_cdev_device *cdev_data =
		container_of(work, struct cpufreq_cdev_device, reg_work);
	struct thermal_cooling_device *cdev;
	struct cpufreq_frequency_table *pos;
	struct cpufreq_policy *policy;
	unsigned int *freq_table;
	int freq_count, idx = 0, ret;

	/* This work may be requested repeatedly as CPUs come online. */
	if (READ_ONCE(cdev_data->cdev))
		return;

	policy = cpufreq_cpu_get(cdev_data->cpu);
	if (!policy) {
		pr_debug("No policy for CPU:%d\n", cdev_data->cpu);
		return;
	}

	freq_count = cpufreq_table_count_valid_entries(policy);
	if (freq_count <= 0) {
		pr_err("CPU%d has no usable frequency table\n", cdev_data->cpu);
		goto err_put_policy;
	}

	freq_table = kmalloc_array(freq_count, sizeof(*freq_table), GFP_KERNEL);
	if (!freq_table)
		goto err_put_policy;

	/* Exclude invalid OPPs, and normalize ascending/unsorted tables. */
	cpufreq_for_each_valid_entry(pos, policy->freq_table)
		freq_table[idx++] = pos->frequency;
	sort(freq_table, freq_count, sizeof(*freq_table), cpufreq_desc_cmp, NULL);

	cdev_data->freq_table = freq_table;
	cdev_data->max_state = freq_count - 1;
	cdev_data->cur_state = 0;

	ret = freq_qos_add_request(&policy->constraints,
				   &cdev_data->qos_max_freq_req, FREQ_QOS_MAX,
				   state_to_cpufreq(cdev_data, 0));
	if (ret < 0) {
		pr_err("CPU%d: cannot register thermal QoS vote: %d\n",
		       cdev_data->cpu, ret);
		goto err_free_table;
	}

	cdev = thermal_cooling_device_register(cdev_data->cdev_name,
					       cdev_data, &cpufreq_cdev_ops);
	if (IS_ERR(cdev)) {
		pr_err("Cdev register failed for %s, ret:%ld\n",
		       cdev_data->cdev_name, PTR_ERR(cdev));
		freq_qos_remove_request(&cdev_data->qos_max_freq_req);
		goto err_free_table;
	}

	cdev_data->policy = policy;
	WRITE_ONCE(cdev_data->cdev, cdev);
	pr_debug("Cdev %s registered\n", cdev_data->cdev_name);
	return;

err_free_table:
	kfree(freq_table);
	cdev_data->freq_table = NULL;
err_put_policy:
	cpufreq_cpu_put(policy);
}

static int cpufreq_cdev_hp_online(unsigned int online_cpu)
{
	struct cpufreq_cdev_device *cdev_data;

	mutex_lock(&qti_cpufreq_cdev_lock);
	list_for_each_entry(cdev_data, &qti_cpufreq_cdev_list, node) {
		if (cdev_data->cpu != online_cpu || READ_ONCE(cdev_data->cdev))
			continue;
		queue_work(system_highpri_wq, &cdev_data->reg_work);
	}
	mutex_unlock(&qti_cpufreq_cdev_lock);
	return 0;
}

/*
 * CPUFreq policies can appear after CPU-online and be destroyed on driver
 * removal.  Drop our QoS vote while the old policy is still alive, before
 * CPUFreq destroys its constraints.
 *
 * Call only after registration work has finished and new registration
 * producers have been quiesced (or while holding qti_cpufreq_cdev_lock).
 */
static void cpufreq_cdev_release(struct cpufreq_cdev_device *cdev_data)
{
	struct thermal_cooling_device *cdev = READ_ONCE(cdev_data->cdev);

	if (!cdev)
		return;

	WRITE_ONCE(cdev_data->cdev, NULL);
	thermal_cooling_device_unregister(cdev);
	if (freq_qos_request_active(&cdev_data->qos_max_freq_req))
		freq_qos_remove_request(&cdev_data->qos_max_freq_req);
	cpufreq_cpu_put(cdev_data->policy);
	cdev_data->policy = NULL;
	kfree(cdev_data->freq_table);
	cdev_data->freq_table = NULL;
	cdev_data->max_state = 0;
	cdev_data->cur_state = 0;
}

/*
 * Policy creation holds internal CPUFreq locks: never register a cooling
 * device synchronously in that callback.  Queue existing registration work.
 * Policy removal uses the blocking notifier and must drain the worker
 * before its policy and QoS constraints can be freed by CPUFreq.
 */
static int cpufreq_cdev_policy_event(struct notifier_block *nb,
				    unsigned long event, void *data)
{
	struct cpufreq_policy *policy = data;
	struct cpufreq_cdev_device *cdev_data;

	if (event != CPUFREQ_CREATE_POLICY &&
	    event != CPUFREQ_REMOVE_POLICY)
		return NOTIFY_DONE;

	mutex_lock(&qti_cpufreq_cdev_lock);
	list_for_each_entry(cdev_data, &qti_cpufreq_cdev_list, node) {
		if (!cpumask_test_cpu(cdev_data->cpu, policy->related_cpus))
			continue;

		if (event == CPUFREQ_CREATE_POLICY) {
			if (!READ_ONCE(cdev_data->cdev))
				queue_work(system_highpri_wq, &cdev_data->reg_work);
		} else {
			/* Keep the list lock: CPU-hotplug cannot queue new work. */
			cancel_work_sync(&cdev_data->reg_work);
			if (cdev_data->policy == policy)
				cpufreq_cdev_release(cdev_data);
		}
	}
	mutex_unlock(&qti_cpufreq_cdev_lock);

	return NOTIFY_OK;
}

static struct notifier_block cpufreq_cdev_policy_nb = {
	.notifier_call = cpufreq_cdev_policy_event,
};

static int cpufreq_cdev_remove(struct platform_device *pdev)
{
	struct cpufreq_cdev_device *cdev_data;

	/* Stop producers before draining the registration workqueue. */
	if (cpufreq_policy_notifier_registered) {
		cpufreq_unregister_notifier(&cpufreq_cdev_policy_nb,
					    CPUFREQ_POLICY_NOTIFIER);
		cpufreq_policy_notifier_registered = false;
	}
	/* Hotplug teardown waits for callbacks: do not hold the list lock. */
	if (cpu_hp_online) {
		cpuhp_remove_state_nocalls(cpu_hp_online);
		cpu_hp_online = 0;
	}

	for (;;) {
		mutex_lock(&qti_cpufreq_cdev_lock);
		if (list_empty(&qti_cpufreq_cdev_list)) {
			cpufreq_cdev_owner = NULL;
			mutex_unlock(&qti_cpufreq_cdev_lock);
			break;
		}
		cdev_data = list_first_entry(&qti_cpufreq_cdev_list,
					    struct cpufreq_cdev_device, node);
		list_del(&cdev_data->node);
		mutex_unlock(&qti_cpufreq_cdev_lock);

		/* No registration work may outlive its QoS policy or devdata. */
		cancel_work_sync(&cdev_data->reg_work);
		cpufreq_cdev_release(cdev_data);
		kfree(cdev_data);
	}
	return 0;
}

static int cpufreq_cdev_probe(struct platform_device *pdev)
{
	struct device_node *np = pdev->dev.of_node;
	struct device_node *cpu_phandle;
	struct cpufreq_cdev_device *cdev_data, *item;
	struct device *cpu_dev;
	int cpu, count, idx, ret;
	bool duplicate;

	count = of_count_phandle_with_args(np, "qcom,cpus", NULL);
	if (count <= 0)
		return count < 0 ? count : -EINVAL;

	mutex_lock(&qti_cpufreq_cdev_lock);
	/* The OEM driver registers a single global CPU-hotplug callback. */
	if (cpufreq_cdev_owner) {
		mutex_unlock(&qti_cpufreq_cdev_lock);
		return -EBUSY;
	}
	cpufreq_cdev_owner = &pdev->dev;
	mutex_unlock(&qti_cpufreq_cdev_lock);

	for (idx = 0; idx < count; idx++) {
		cpu_phandle = of_parse_phandle(np, "qcom,cpus", idx);
		if (!cpu_phandle) {
			ret = -EINVAL;
			goto err_remove;
		}

		for_each_possible_cpu(cpu) {
			cpu_dev = get_cpu_device(cpu);
			if (cpu_dev && cpu_dev->of_node == cpu_phandle)
				break;
		}
		of_node_put(cpu_phandle);
		if (cpu >= nr_cpu_ids) {
			ret = -EPROBE_DEFER;
			goto err_remove;
		}

		mutex_lock(&qti_cpufreq_cdev_lock);
		duplicate = false;
		list_for_each_entry(item, &qti_cpufreq_cdev_list, node) {
			if (item->cpu == cpu) {
				duplicate = true;
				break;
			}
		}
		if (duplicate) {
			mutex_unlock(&qti_cpufreq_cdev_lock);
			continue;
		}
		cdev_data = kzalloc(sizeof(*cdev_data), GFP_KERNEL);
		if (!cdev_data) {
			mutex_unlock(&qti_cpufreq_cdev_lock);
			ret = -ENOMEM;
			goto err_remove;
		}
		cdev_data->cpu = cpu;
		mutex_init(&cdev_data->state_lock);
		snprintf(cdev_data->cdev_name, THERMAL_NAME_LENGTH,
			 CPUFREQ_CDEV_NAME, cpu);
		INIT_WORK(&cdev_data->reg_work, cpufreq_cdev_register);
		list_add_tail(&cdev_data->node, &qti_cpufreq_cdev_list);
		mutex_unlock(&qti_cpufreq_cdev_lock);
	}

	/* Register the policy notifier before CPU-online callbacks fire. */
	ret = cpufreq_register_notifier(&cpufreq_cdev_policy_nb,
					CPUFREQ_POLICY_NOTIFIER);
	if (ret)
		goto err_remove;
	cpufreq_policy_notifier_registered = true;

	/* Callbacks can queue work; the list is now fully initialized. */
	ret = cpuhp_setup_state(CPUHP_AP_ONLINE_DYN, "thermal-cpu/cdev:online",
				cpufreq_cdev_hp_online, NULL);
	if (ret < 0)
		goto err_remove;
	cpu_hp_online = ret;
	return 0;

err_remove:
	cpufreq_cdev_remove(pdev);
	return ret;
}

static const struct of_device_id cpufreq_cdev_match[] = {
	{.compatible = "qcom,cpufreq-cdev"},
	{}
};

static struct platform_driver cpufreq_cdev_driver = {
	.probe          = cpufreq_cdev_probe,
	.remove         = cpufreq_cdev_remove,
	.driver         = {
		.name   = CPUFREQ_CDEV,
		.of_match_table = cpufreq_cdev_match,
	},
};

module_platform_driver(cpufreq_cdev_driver);
MODULE_DESCRIPTION("Qualcomm Technologies, Inc. cpufreq cooling driver");
MODULE_LICENSE("GPL v2");
