// SPDX-License-Identifier: GPL-2.0-only
/*
 * Kernel DRM DisplayPort LTTPR helper compatibility for Xiaomi OEM Linux 5.10.
 *
 * Based on the actual Linux DRM DP helper behavior (Linux v6.1,
 * drivers/gpu/drm/display/drm_dp_helper.c). Keep it local to msm_drm.o:
 * the pinned OEM DRM core does not export these helpers.
 */

#include <linux/bitops.h>
#include <linux/errno.h>
#include <linux/log2.h>
#include <linux/string.h>

#include "dp_lttpr_compat.h"

int pe_waipio_dp_read_lttpr_common_caps(struct drm_dp_aux *aux,
		const u8 dpcd[DP_RECEIVER_CAP_SIZE],
		u8 caps[DP_LTTPR_COMMON_CAP_SIZE])
{
	int block_size, offset, ret;

	if (!aux || !dpcd || !caps)
		return -EINVAL;

	/* Some older sinks corrupt LTTPR reads larger than one DPCD byte. */
	block_size = dpcd[DP_DPCD_REV] < 0x14 ? 1 : DP_LTTPR_COMMON_CAP_SIZE;
	memset(caps, 0, DP_LTTPR_COMMON_CAP_SIZE);

	for (offset = 0; offset < DP_LTTPR_COMMON_CAP_SIZE;
	     offset += block_size) {
		ret = drm_dp_dpcd_read(aux,
				DP_LT_TUNABLE_PHY_REPEATER_FIELD_DATA_STRUCTURE_REV +
				offset, caps + offset, block_size);
		if (ret < 0)
			return ret;
		if (ret != block_size)
			return -EIO;
	}

	return 0;
}

int pe_waipio_dp_lttpr_count(const u8 caps[DP_LTTPR_COMMON_CAP_SIZE])
{
	u8 count;

	if (!caps)
		return -EINVAL;

	count = caps[DP_PHY_REPEATER_CNT -
			DP_LT_TUNABLE_PHY_REPEATER_FIELD_DATA_STRUCTURE_REV];
	switch (hweight8(count)) {
	case 0:
		return 0;
	case 1:
		return 8 - ilog2(count);
	case 8:
		return -ERANGE;
	default:
		return -EINVAL;
	}
}
