/* SPDX-License-Identifier: GPL-2.0-only */
/*
 * Local DisplayPort LTTPR compatibility for the OEM Linux 5.10 DRM ABI.
 * Algorithm follows the upstream Linux DRM DP helper, not an empty shim.
 */
#ifndef __PE_WAIPIO_DP_LTTPR_COMPAT_H__
#define __PE_WAIPIO_DP_LTTPR_COMPAT_H__

#include <drm/drm_dp_helper.h>

#ifndef DP_LTTPR_COMMON_CAP_SIZE
#define DP_LTTPR_COMMON_CAP_SIZE 8
#endif

#if !defined(DP_LT_TUNABLE_PHY_REPEATER_FIELD_DATA_STRUCTURE_REV) || \
    !defined(DP_PHY_REPEATER_CNT)
#error "OEM DRM headers lack LTTPR register definitions"
#endif

int pe_waipio_dp_read_lttpr_common_caps(struct drm_dp_aux *aux,
		const u8 dpcd[DP_RECEIVER_CAP_SIZE],
		u8 caps[DP_LTTPR_COMMON_CAP_SIZE]);
int pe_waipio_dp_lttpr_count(const u8 caps[DP_LTTPR_COMMON_CAP_SIZE]);

#endif /* __PE_WAIPIO_DP_LTTPR_COMPAT_H__ */
