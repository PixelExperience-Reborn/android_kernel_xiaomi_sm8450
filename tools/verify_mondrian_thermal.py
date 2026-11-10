#!/usr/bin/env python3
"""Source-level safety checks for Xiaomi mondrian CPU voltage cooling.

These checks complement actual LLVM compilation; they do not establish
real-world SM8475 thermal response, power consumption or battery safety.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "drivers/thermal/qcom/cpu_voltage_cooling.c"
MAKE = ROOT / "drivers/thermal/qcom/Makefile"
CONFIG = ROOT / "arch/arm64/configs/vendor/mondrian_GKI.config"
GPU_SRC = ROOT / "drivers/thermal/qcom/qti_devfreq_cdev.c"
CPUFREQ_SRC = ROOT / "drivers/thermal/qcom/qti_cpufreq_cdev.c"
PAUSE_SRC = ROOT / "drivers/thermal/qcom/thermal_pause.c"
WALT_PAUSE_SRC = ROOT / "kernel/sched/walt/walt_pause.c"


def require(condition, detail):
    if not condition:
        raise SystemExit("[FAIL] mondrian thermal: " + detail)


def main():
    code = SRC.read_text(encoding="utf-8")
    make = MAKE.read_text(encoding="utf-8")
    config = CONFIG.read_text(encoding="utf-8")
    gpu = GPU_SRC.read_text(encoding="utf-8")
    cpufreq = CPUFREQ_SRC.read_text(encoding="utf-8")
    pause = PAUSE_SRC.read_text(encoding="utf-8")
    walt = WALT_PAUSE_SRC.read_text(encoding="utf-8")

    require("CONFIG_QTI_CPUFREQ_CDEV=m" in config,
            "OEM CPUFreq cooling module must remain selected")
    require("obj-$(CONFIG_QTI_CPUFREQ_CDEV) += qti_cpufreq_cdev.o" in make,
            "OEM CPUFreq cooling module must remain linked")
    cpu_register = cpufreq.split("static void cpufreq_cdev_register(", 1)[1].split(
        "static int cpufreq_cdev_hp_online(", 1)[0]
    cpu_remove = cpufreq.split("static int cpufreq_cdev_remove(", 1)[1].split(
        "static int cpufreq_cdev_probe(", 1)[0]
    cpu_probe = cpufreq.split("static int cpufreq_cdev_probe(", 1)[1].split(
        "static const struct of_device_id", 1)[0]
    cpu_set = cpufreq.split("static int cpufreq_cdev_set_state(", 1)[1].split(
        "static int cpufreq_cdev_get_state(", 1)[0]
    require("cpufreq_for_each_valid_entry(" in cpu_register and
            "sort(freq_table, freq_count," in cpu_register,
            "CPUFreq limits must exclude invalid entries and be descending")
    require(cpu_register.index("ret = freq_qos_add_request(") <
            cpu_register.index("if (ret < 0)") <
            cpu_register.index("thermal_cooling_device_register("),
            "CPUFreq QoS creation must be checked before cooling registration")
    require("freq_qos_remove_request(" in cpu_register and
            "cpufreq_cpu_put(policy);" in cpu_register and
            "cdev_data->freq_table = NULL;" in cpu_register,
            "CPUFreq failed registration must release policy, QoS and table")
    require("mutex_lock(&cdev_data->state_lock);" in cpu_set and
            cpu_set.index("freq_qos_update_request(") <
            cpu_set.index("cdev_data->cur_state = state;"),
            "CPUFreq cooling state must change only after successful QoS vote")
    require(cpu_remove.index("cpuhp_remove_state_nocalls(") <
            cpu_remove.index("mutex_lock(&qti_cpufreq_cdev_lock)"),
            "CPU hotplug callbacks must stop outside the list mutex")
    cpu_release = cpufreq.split("static void cpufreq_cdev_release(", 1)[1].split(
        "static int cpufreq_cdev_policy_event(", 1)[0]
    require(cpu_remove.index("cancel_work_sync(") <
            cpu_remove.index("cpufreq_cdev_release(cdev_data);"),
            "CPUFreq registration work must stop before teardown")
    require(cpu_release.index("thermal_cooling_device_unregister(") <
            cpu_release.index("freq_qos_remove_request(") <
            cpu_release.index("cpufreq_cpu_put("),
            "CPUFreq cooling must unregister before freeing policy QoS")
    require("cdev_data->policy = NULL;" in cpu_release and
            "cdev_data->freq_table = NULL;" in cpu_release,
            "CPUFreq stale policy and table pointers must be cleared")
    require("cpufreq_cdev_owner = &pdev->dev;" in cpu_probe and
            "of_node_put(cpu_phandle);" in cpu_probe and
            "bool duplicate;" in cpu_probe,
            "CPUFreq probe must have one owner and release matched CPU phandles")
    policy_notifier = cpufreq.split(
        "static int cpufreq_cdev_policy_event(", 1)[1].split(
        "static struct notifier_block cpufreq_cdev_policy_nb", 1)[0]
    require("CPUFREQ_CREATE_POLICY" in policy_notifier and
            "CPUFREQ_REMOVE_POLICY" in policy_notifier and
            "queue_work(system_highpri_wq, &cdev_data->reg_work);" in policy_notifier and
            "cpumask_test_cpu(cdev_data->cpu, policy->related_cpus)" in policy_notifier,
            "CPUFreq policy creation must retry cooling registration asynchronously")
    require(policy_notifier.index("cancel_work_sync(") <
            policy_notifier.index("cpufreq_cdev_release(cdev_data);"),
            "CPUFreq policy removal must quiesce work before releasing QoS")
    require(cpu_probe.index("cpufreq_register_notifier(") <
            cpu_probe.index("cpuhp_setup_state("),
            "policy notifier must be installed before hotplug callbacks")
    require("cpufreq_unregister_notifier(" in cpu_remove and
            cpu_remove.index("cpufreq_unregister_notifier(") <
            cpu_remove.index("cpuhp_remove_state_nocalls(") <
            cpu_remove.index("cancel_work_sync("),
            "policy/hotplug event producers must stop before freeing worker state")

    require("CONFIG_QTI_CPU_PAUSE_COOLING_DEVICE=m" in config and
            "obj-$(CONFIG_QTI_CPU_PAUSE_COOLING_DEVICE) += thermal_pause.o" in make,
            "Qualcomm thermal pause must still be built for mondrian")
    pause_register = pause.split("static void thermal_pause_register_cdev(", 1)[1].split(
        "static int thermal_pause_remove(struct platform_device *pdev);", 1)[0]
    pause_probe = pause.split("static int thermal_pause_probe(", 1)[1].split(
        "static int thermal_pause_remove(struct platform_device *pdev)\n{", 1)[0]
    pause_remove = pause.split("static int thermal_pause_remove(struct platform_device *pdev)\n{", 1)[1].split(
        "static const struct of_device_id thermal_pause_match", 1)[0]
    pause_resume = pause.split("static int thermal_resume_work(", 1)[1].split(
        "static void thermal_pause_update_work(", 1)[0]
    pause_update = pause.split("static void thermal_pause_update_work(", 1)[1].split(
        "static int thermal_pause_set_cur_state(", 1)[0]
    pause_get = pause.split("static int thermal_pause_get_cur_state(", 1)[1].split(
        "static int thermal_pause_get_max_state(", 1)[0]
    require("if (READ_ONCE(thermal_pause_cdev->cdev))" in pause_register,
            "Repeated CPU-online callbacks must not double-register a cooling device")
    require("if (thermal_pause_owner)" in pause_probe and
            "thermal_pause_remove(pdev);" in pause_probe and
            "INIT_LIST_HEAD(&thermal_pause_cdev_list);" not in pause_probe,
            "Thermal pause probes must use one owner and undo partial initialization")
    require(pause_remove.index("cpuhp_remove_state_nocalls(") <
            pause_remove.index("cancel_work_sync(") <
            pause_remove.index("thermal_cooling_device_unregister(") <
            pause_remove.index("cancel_delayed_work_sync(") <
            pause_remove.index("thermal_resume_work(thermal_pause_cdev);") <
            pause_remove.index("list_del("),
            "Thermal pause removal must stop all work and release WALT votes before detaching")
    require(pause_remove.index("mutex_unlock(&cpus_pause_lock);") <
            pause_remove.index("cancel_delayed_work_sync("),
            "Do not synchronously cancel work while holding the worker's mutex")
    require("walt_resume_cpus(" in pause_resume and
            "cpumask_copy(&cpus_in_max_cooling_level" in pause_resume and
            "update_ref_counts(&requested_cpus, false);" in walt,
            "Thermal teardown must use the actual refcounted OEM WALT resume path")
    require("static DEFINE_MUTEX(thermal_pause_transition_lock);" in pause,
            "Thermal WALT transitions need a separate serialisation lock")
    require(pause_update.index("mutex_lock(&thermal_pause_transition_lock);") <
            pause_update.index("mutex_lock(&cpus_pause_lock);") <
            pause_update.index("thermal_resume_work(thermal_pause_cdev);") <
            pause_update.index("mutex_unlock(&cpus_pause_lock);\\n\\tmutex_unlock(&thermal_pause_transition_lock);"),
            "Cooling workers must serialise across the unlocked WALT call")
    require(pause_remove.index("cancel_delayed_work_sync(") <
            pause_remove.index("mutex_lock(&thermal_pause_transition_lock);") <
            pause_remove.index("mutex_lock(&cpus_pause_lock);", pause_remove.index("mutex_lock(&thermal_pause_transition_lock);")) <
            pause_remove.index("thermal_resume_work(thermal_pause_cdev);") <
            pause_remove.index("mutex_unlock(&thermal_pause_transition_lock);"),
            "Teardown must drain work before taking the transition lock for WALT release")
    require("*level = READ_ONCE(thermal_pause_cdev->thermal_pause_level);" in pause_get,
            "Thermal current-state getter must not race plain unlocked reads with WALT work")

    require("CONFIG_QTI_DEVFREQ_CDEV=m" in config,
            "OEM GPU devfreq cooling module is not selected")
    require("obj-$(CONFIG_QTI_DEVFREQ_CDEV) += qti_devfreq_cdev.o" in make,
            "OEM GPU cooling driver is not linked")
    work = gpu.split("static void devfreq_cdev_work(", 1)[1].split(
        "static int devfreq_cdev_probe(", 1)[0]
    gpu_remove = gpu.split("static int devfreq_cdev_remove(", 1)[1].split(
        "static const struct of_device_id", 1)[0]
    require(work.index("if (freq_ct <= 0)") < work.index("kcalloc(freq_ct"),
            "GPU OPP count must be validated before allocating a table")
    require("kfree(freq_table);" in work and
            "cdev_data->freq_table = NULL;" in work,
            "GPU error path must free its actual OPP table")
    require(work.index("dev_pm_qos_add_request(") <
            work.index("dev_pm_qos_remove_request("),
            "GPU QoS removal cannot precede successful insertion")
    require("platform_set_drvdata(pdev, cdev_data);" in gpu,
            "GPU cooling device cannot use a global state pointer")
    require(gpu_remove.index("cancel_delayed_work_sync(") <
            gpu_remove.index("thermal_cooling_device_unregister("),
            "GPU delayed registration must stop before teardown")
    require("of_node_put(cdev_data->np);" in gpu_remove,
            "GPU cooling must release its Device Tree node")

    require("CONFIG_QTI_CPU_VOLTAGE_COOLING_DEVICE=m" in config,
            "OEM cooling module is not selected")
    require("obj-$(CONFIG_QTI_CPU_VOLTAGE_COOLING_DEVICE) += cpu_voltage_cooling.o" in make,
            "OEM cooling driver is no longer built")
    probe = code.split("static int cc_cooling_probe(", 1)[1].split(
        "static int cc_cooling_remove(", 1)[0]
    remove = code.split("static int cc_cooling_remove(struct platform_device *pdev)\n{", 1)[1]
    setter = code.split("static int cc_set_cur_state(", 1)[1].split(
        "static int cc_get_cur_state(", 1)[0]
    opp = code.split("static struct cc_limits_data *opp_init(", 1)[1].split(
        "static int cc_init(", 1)[0]

    require("int cpu_map[CPU_MAP_CT] = { -1, -1 };" in probe,
            "every DT child must initialize its CPU map")
    require("if (!dev_phandle)" in probe and "if (cpu_map[idx] < 0)" in probe,
            "missing or unmatched CPU phandles must fail safely")
    require(probe.index("of_node_put(dev_phandle);") <
            probe.index("if (cpu_map[idx] < 0)"),
            "CPU phandle reference must be released")
    require("of_node_put(subsys_np);" in probe and "cc_cooling_remove(pdev);" in probe,
            "probe error must drop the child ref and roll back completed devices")
    require("struct device" in code and "*owner;" in code and
            "cc_cdev->owner = dev;" in code and
            "if (cc_cdev->owner != &pdev->dev)" in remove,
            "cooling resources must be released only by their owning device")
    require("mutex_lock(&cc_cdev->state_lock);" in setter and
            "mutex_unlock(&cc_cdev->state_lock);" in setter,
            "CPU QoS state transitions must be serialized")
    require(setter.index("freq_qos_update_request(") <
            setter.index("cc_cdev->thermal_state = state;"),
            "do not publish cooling state before QoS update")
    require("cc_cdev->map_freq[old_state].frequency[idx]" in setter,
            "failed QoS transitions must roll back to the old CPU cap")
    require("mutex_init(&cc_cdev->state_lock);" in opp,
            "thermal state mutex was not initialized")
    require("ret = -ENOMEM;" in opp and "return ERR_PTR(ret);" in opp,
            "OPP failures must preserve their actual error codes")
    print("[PASS] mondrian OEM CPU voltage, CPUFreq hotplug, WALT thermal pause and GPU devfreq safety checks")
    print("[PENDING] LLVM build and runtime thermal transitions on SM8475")


if __name__ == "__main__":
    main()
