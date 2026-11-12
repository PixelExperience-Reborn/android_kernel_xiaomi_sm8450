/* SPDX-License-Identifier: GPL-2.0-only */
/*
 * Copyright (c) Qualcomm Innovation Center, Inc. and/or its subsidiaries.
 */

#ifndef __QCOM_DISPLAY_INTERNAL_H__
#define __QCOM_DISPLAY_INTERNAL_H__

#include <linux/types.h>
#include <linux/notifier.h>
#include <linux/clk/qcom.h>
#include <linux/ioport.h>
#include <linux/pinctrl/qcom-pinctrl.h>
#include <linux/qtee_shmbridge.h>
#include <linux/soc/qcom/llcc-qcom.h>
#include <linux/soc/qcom/msm_mmrm.h>
#include <linux/qcom-iommu-util.h>
#include <linux/qcom_scm.h>
#include <linux/soc/qcom/panel_event_notifier.h>
#include <linux/soc/qcom/altmode-glink.h>
#include <linux/ipc_logging.h>
#include <soc/qcom/of_common.h>
#include <linux/errno.h>
#include <linux/of.h>

#define MMRM_CLIENT_DATA_FLAG_RESERVE_ONLY  0x0001
#define MMRM_CLK_CLIENT_NAME_SIZE  128
#define PFN_DEV (1ULL << (BITS_PER_LONG_LONG - 3))
#define DMA_ATTR_DELAYED_UNMAP      (1UL << 17)
#define DMA_ATTR_QTI_SMMU_PROXY_MAP (1UL << 18)

/* enum sid_switch_direction is provided by OEM <linux/qcom-iommu-util.h>. */

enum subset_part_type {
	PART_UNKNOWN,
	PART_GPU,
	PART_VIDEO,
	PART_CAMERA,
	PART_DISPLAY,
	PART_AUDIO,
	PART_MODEM,
	PART_WLAN,
	PART_COMP,
	PART_SENSORS,
	PART_NPU,
	PART_SPSS,
	PART_NAV,
	PART_COMP1,
	PART_DISPLAY1,
	PART_NSP,
	PART_EVA,
	NUM_PARTS_MAX,
};

/* Clock flags come from the OEM clock API, not a second enum definition. */

/* MMRM enums, callbacks and structs must match the real OEM 5.10 ABI.
 * Their definitions are in <linux/soc/qcom/msm_mmrm.h>; do not redeclare
 * newer incompatible CESTA layouts in an external display module.
 */

/* SDE secure-memory ownership is managed by the real OEM SCM API in
 * <linux/qcom_scm.h>. Do not substitute a no-op success path here.
 */

/**
 * Enum describing the various staling modes available for clients to use.
 */
enum llcc_staling_mode {
	LLCC_STALING_MODE_CAPACITY, /* Default option on reset */
	LLCC_STALING_MODE_NOTIFY,
	LLCC_STALING_MODE_MAX
};

enum llcc_staling_notify_op {
	LLCC_NOTIFY_STALING_WRITEBACK,
	LLCC_NOTIFY_STALING_NO_WRITEBACK,
	LLCC_NOTIFY_STALING_OPS_MAX
};

struct llcc_staling_mode_params {
	enum llcc_staling_mode staling_mode;
	union {
		/* STALING_MODE_CAPACITY needs no params */
		struct staling_mode_notify_params {
			u8 staling_distance;
			enum llcc_staling_notify_op op;
		} notify_params;
	};
};

/* QTEE shared-memory state, struct qtee_shm and secure-buffer VMIDs are
 * supplied together by <linux/qtee_shmbridge.h>. In particular, never force
 * the bridge to appear disabled when the OEM SCM driver has enabled it.
 * GPIO resource lookup likewise uses the real OEM pinctrl implementation.
 */

/* Event notifier functions come from <linux/soc/qcom/panel_event_notifier.h>. */

static int llcc_configure_staling_mode(struct llcc_slice_desc *desc,
				struct llcc_staling_mode_params *p)
{
	return -EINVAL;
}

static int llcc_notif_staling_inc_counter(struct llcc_slice_desc *desc)
{
	return -EINVAL;
}



/* Logging uses the real OEM <linux/ipc_logging.h> implementation. */

/* DDR type parsing is provided by native OEM <soc/qcom/of_common.h>. */
#endif
