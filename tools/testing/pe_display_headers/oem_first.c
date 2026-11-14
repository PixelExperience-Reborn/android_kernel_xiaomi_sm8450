// SPDX-License-Identifier: GPL-2.0-only
/* Exercise OEM-first includes used by the SDE power and catalog code. */
#include <linux/ioport.h>
#include <linux/clk/qcom.h>
#include <linux/pinctrl/qcom-pinctrl.h>
#include <linux/qtee_shmbridge.h>
#include <soc/qcom/of_common.h>
#include <soc/qcom/secure_buffer.h>
#include "qcom_display_internal.h"
#include "hfi/hfi_defs_common.h"
#include "hfi/hfi_pack_unpack_common.h"
#include "hfi/hfi_defs_display_color.h"
