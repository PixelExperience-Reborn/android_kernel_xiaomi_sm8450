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


def require(condition, detail):
    if not condition:
        raise SystemExit("[FAIL] mondrian thermal: " + detail)


def main():
    code = SRC.read_text(encoding="utf-8")
    make = MAKE.read_text(encoding="utf-8")
    config = CONFIG.read_text(encoding="utf-8")

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
    print("[PASS] mondrian OEM CPU-voltage cooling DT, QoS and lifetime source checks")
    print("[PENDING] LLVM build and runtime thermal transitions on SM8475")


if __name__ == "__main__":
    main()
