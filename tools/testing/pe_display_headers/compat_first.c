// SPDX-License-Identifier: GPL-2.0-only
/* Exercise the include order used by SDE KMS through sde_cesta.h. */
#include "qcom_display_internal.h"
#include <linux/clk/qcom.h>
#include <linux/pinctrl/qcom-pinctrl.h>
#include <linux/qtee_shmbridge.h>
#include <soc/qcom/of_common.h>
#include <soc/qcom/secure_buffer.h>
#include "hfi/hfi_defs_common.h"
