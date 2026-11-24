// SPDX-License-Identifier: GPL-2.0-only
/* Xiaomi M11A, mondrian board 14. Packet indices are local to each timing. */
#include <linux/delay.h>
#include <linux/of.h>
#include <linux/slab.h>
#include <asm/unaligned.h>
#include <linux/soc/qcom/smem.h>
#include <video/mipi_display.h>
#include "../dsi/dsi_display.h"
#include "mondrian_fod.h"

#define M11A_LHBM "mi,mdss-dsi-local-hbm-"
#define M11A_MAX_DBV 4095

/* Alpha table from MiCode/vendor_opensource_display-drivers, bf0d5e23.
 * Copyright (c) 2020, The Linux Foundation. All rights reserved.
 * Copyright (c) 2020 XiaoMi, Inc. All rights reserved.
 */
static const u16 m11a_alpha[] = {
	0x000, 0x009, 0x00a, 0x020, 0x098, 0x0bf, 0x16c, 0x206, 0x2b9, 0x2d4,
	0x2ec, 0x302, 0x316, 0x338, 0x34a, 0x369, 0x387, 0x3b3, 0x3cf, 0x3ea,
	0x414, 0x43c, 0x464, 0x48c, 0x4b3, 0x4ca, 0x4d2, 0x4e8, 0x4fe, 0x505,
	0x51a, 0x52f, 0x543, 0x557, 0x56b, 0x57e, 0x591, 0x5b3, 0x5c6, 0x5d8,
	0x5ea, 0x5fc, 0x60d, 0x61f, 0x63f, 0x650, 0x66f, 0x680, 0x690, 0x6af,
	0x6b5, 0x6c5, 0x6d5, 0x6e4, 0x6f3, 0x702, 0x711, 0x707, 0x716, 0x724,
	0x733, 0x741, 0x74f, 0x75d, 0x76b, 0x779, 0x787, 0x794, 0x7a2, 0x7af,
	0x7bc, 0x7c9, 0x7d6, 0x7e3, 0x7f0, 0x7fd, 0x80a, 0x816, 0x823, 0x82f,
	0x854, 0x847, 0x854, 0x879, 0x885, 0x891, 0x89c, 0x8a8, 0x8b4, 0x8bf,
	0x8cb, 0x8d6, 0x8e2, 0x906, 0x911, 0x91d, 0x928, 0x933, 0x93e, 0x949,
	0x954, 0x95e, 0x969, 0x974, 0x97f, 0x989, 0x994, 0x985, 0x9a9, 0x9b3,
	0x9bd, 0x9af, 0x9d2, 0x9c3, 0x9cd, 0x9d7, 0x9e1, 0x9eb, 0x9f5, 0x9ff,
	0xa09, 0xa13, 0xa1d, 0xa26, 0xa30, 0xa3a, 0xa43, 0xa4d, 0xa56, 0xa60,
	0xa69, 0xa72, 0xa7c, 0xa85, 0xa8e, 0xa98, 0xaa1, 0xaaa, 0xab3, 0xabc,
	0xac5, 0xace, 0xad7, 0xae0, 0xae9, 0xaf2, 0xafb, 0xb04, 0xb0c, 0xb15,
	0xb1e, 0xb27, 0xb2f, 0xb38, 0xb40, 0xb49, 0xb52, 0xb5a, 0xb63, 0xb6b,
	0xb73, 0xb7c, 0xb84, 0xb8c, 0xb95, 0xb9d, 0xba5, 0xbae, 0xbb6, 0xbbe,
	0xbc6, 0xbce, 0xbd6, 0xbde, 0xbe6, 0xbee, 0xbf6, 0xc17, 0xc06, 0xc0e,
	0xc2f, 0xc1e, 0xc26, 0xc2e, 0xc35, 0xc56, 0xc45, 0xc66, 0xc6d, 0xc75,
	0xc7d, 0xc84, 0xc8c, 0xc93, 0xc9b, 0xca3, 0xcaa, 0xcb2, 0xcb9, 0xcc1,
	0xcc8, 0xccf, 0xcd7, 0xcde, 0xce6, 0xced, 0xcf4, 0xcfc, 0xd03, 0xd0a,
	0xd11, 0xd19, 0xd20, 0xd27, 0xd2e, 0xd35, 0xd3d, 0xd44, 0xd4b, 0xd52,
	0xd59, 0xd60, 0xd67, 0xd6e, 0xd75, 0xd7c, 0xd83, 0xd8a, 0xd91, 0xd98,
	0xd9f, 0xda6, 0xdac, 0xdb3, 0xdba, 0xdc1, 0xdaf, 0xdcf, 0xdd5, 0xdc3,
	0xde3, 0xdd1, 0xdf0, 0xdf7, 0xde5, 0xdeb, 0xe0b, 0xe12, 0xdff, 0xe1f,
	0xe0c, 0xe13, 0xe33, 0xe39, 0xe40, 0xe2d, 0xe4d, 0xe53, 0xe5a, 0xe60,
	0xe67, 0xe54, 0xe73, 0xe61, 0xe80, 0xe6e, 0xe8d, 0xe93, 0xe9a, 0xea0,
	0xea6, 0xe94, 0xeb3, 0xeb9, 0xec0, 0xec6, 0xecc, 0xed2, 0xed8, 0xedf,
	0xee5, 0xeeb, 0xef1, 0xef7, 0xefe, 0xf04, 0xf0a, 0xf10, 0xf16, 0xf1c,
	0xf22, 0xf28, 0xf2e, 0xf34, 0xf3a, 0xf40, 0xf46, 0xf4c, 0xf52, 0xf58,
	0xf5e, 0xf64, 0xf6a, 0xf70, 0xf76, 0xf7c, 0xf82, 0xf88, 0xf8e, 0xf94,
	0xf99, 0xf9f, 0xfa5, 0xfab, 0xfb1, 0xfb7, 0xfbc, 0xfc2, 0xfc8, 0xfce,
	0xfd8, 0xfde, 0xfe4, 0xfef, 0xfef, 0xff5, 0xffa, 0xfff,
};

struct m11a_values {
	u16 dbv;
	u8 rgb[6];
	bool keep_green;
};

enum update_reg {
	PATCH_DBV = BIT(0), PATCH_ALPHA = BIT(1), PATCH_RGB = BIT(2), PATCH_DF = BIT(3),
};

static struct device_node *m11a_timing(struct dsi_panel *panel)
{
	struct device_node *timings, *node;
	u32 hz;
	struct dsi_mode_info *mode;

	if (!panel->cur_mode)
		return NULL;
	mode = &panel->cur_mode->timing;
	if (mode->h_active != 1440 || mode->v_active != 3200 ||
	    (mode->refresh_rate != 60 && mode->refresh_rate != 90 && mode->refresh_rate != 120))
		return NULL;
	timings = of_get_child_by_name(panel->panel_of_node, "qcom,mdss-dsi-display-timings");
	if (!timings)
		return NULL;
	for_each_available_child_of_node(timings, node) {
		if (!of_property_read_u32(node, "qcom,mdss-dsi-panel-framerate", &hz) &&
		    hz == mode->refresh_rate)
			break;
	}
	of_node_put(timings);
	return node;
}

static int m11a_white_rgb(struct dsi_display *d, enum m11a_target target, u8 *out)
{
	const u8 *table;
	size_t size;
	u32 flat_on;
	u8 flat;
	unsigned int i, offset;
	bool low = target == M11A_WHITE_110;
	int rc;

	table = qcom_smem_get(QCOM_SMEM_HOST_ANY, 498, &size);
	if (IS_ERR(table))
		return PTR_ERR(table);
	if (!table || size < 24)
		return -ENODATA;
	if (of_property_read_u32(d->panel->panel_of_node,
				 "mi,mdss-dsi-panel-flatmode-on-status-value", &flat_on))
		return -ENODATA;
	rc = m11a_dcs_read_locked(d, 0x5f, &flat, sizeof(flat));
	if (rc)
		return rc;
	offset = (low ? 12 : 0) + (flat == flat_on ? 0 : 6);
	for (i = 0; i < 6; i += 2) {
		u16 val = get_unaligned_be16(table + offset + i);

		if (!val || val > M11A_MAX_DBV || (low && val > M11A_MAX_DBV - 70))
			return -ENODATA;
		put_unaligned_be16(val + (low ? 70 : 0), out + i);
	}
	return 0;
}

/* Validate the complete stream and its update table before the first write. */
static int m11a_update(struct dsi_panel_cmd_set *set, const __be32 *cells,
		       int bytes, unsigned int expected, const struct m11a_values *v)
{
	unsigned int seen = 0;

	if (bytes < 0 || bytes % (3 * sizeof(*cells)))
		return -EINVAL;
	while (bytes) {
		u32 reg = be32_to_cpup(cells++), idx = be32_to_cpup(cells++);
		u32 len = be32_to_cpup(cells++), bit;
		u8 *p;

		if (!v || idx >= set->count || set->cmds[idx].msg.tx_len != len + 1ULL)
			return -EINVAL;
		p = (u8 *)set->cmds[idx].msg.tx_buf;
		if (*p++ != reg || (reg == 0xd0 ? len != 6 : len != 2))
			return -EINVAL;
		switch (reg) {
		case 0x51:
			bit = PATCH_DBV;
			put_unaligned_be16(v->dbv, p);
			break;
		case 0x87:
			bit = PATCH_ALPHA;
			put_unaligned_be16(v->dbv < ARRAY_SIZE(m11a_alpha) ?
				0x1000 | m11a_alpha[v->dbv] : 0x1fff, p);
			break;
		case 0xd0:
			bit = PATCH_RGB;
			if (!v->keep_green)
				memcpy(p, v->rgb, sizeof(v->rgb));
			break;
		case 0xdf:
			bit = PATCH_DF;
			put_unaligned_be16(4 * max_t(u16, 327, v->dbv), p);
			break;
		default:
			return -EINVAL;
		}
		if (seen & bit)
			return -EINVAL;
		seen |= bit;
		bytes -= 3 * sizeof(*cells);
	}
	return seen == expected ? 0 : -EINVAL;
}

static int m11a_send(struct dsi_display *d, const char *prop, unsigned int expected,
		     const struct m11a_values *v, bool *started)
{
	struct device_node *node;
	struct dsi_panel_cmd_set set = {};
	const __be32 *updates = NULL;
	const u8 *data, *p;
	int size = 0, left, bytes = 0, rc, i;
	char key[96];
	const char *state;
	bool lp;

	rc = m11a_host_ready(d);
	if (rc)
		return rc;
	node = m11a_timing(d->panel);
	if (!node)
		return -ENODEV;
	rc = -EINVAL;
	data = of_get_property(node, prop, &size);
	snprintf(key, sizeof(key), "%s-state", prop);
	if (!data || size <= 0 || of_property_read_string(node, key, &state))
		goto out_node;
	lp = !strcmp(state, "dsi_lp_mode");
	if (!lp && strcmp(state, "dsi_hs_mode"))
		goto out_node;
	p = data;
	for (left = size; left; ) {
		u16 len;

		if (left < 7)
			goto out_node;
		len = get_unaligned_be16(p + 5);
		if (!len || len > left - 7 || p[2] != 0 || (p[1] >> 6) >= d->ctrl_count ||
		    (p[0] != MIPI_DSI_DCS_SHORT_WRITE && p[0] != MIPI_DSI_DCS_SHORT_WRITE_PARAM &&
		     p[0] != MIPI_DSI_DCS_LONG_WRITE) || (left == 7 + len && (p[3] & MIPI_DSI_MSG_BATCH_COMMAND)))
			goto out_node;
		p += 7 + len;
		left -= 7 + len;
		set.count++;
	}
	set.cmds = kcalloc(set.count, sizeof(*set.cmds), GFP_KERNEL);
	if (!set.cmds) {
		rc = -ENOMEM;
		goto out_node;
	}
	/* Each transfer uses this request's private copy of the immutable DT. */
	p = kmemdup(data, size, GFP_KERNEL);
	if (!p) {
		rc = -ENOMEM;
		goto out_set;
	}
	data = p;
	for (i = 0; i < set.count; i++) {
		struct dsi_cmd_desc *cmd = &set.cmds[i];

		cmd->msg.type = p[0];
		cmd->ctrl = p[1] >> 6;
		cmd->msg.channel = p[2];
		cmd->msg.flags = p[3] | (lp ? MIPI_DSI_MSG_USE_LPM : 0);
		cmd->last_command = !(p[3] & MIPI_DSI_MSG_BATCH_COMMAND);
		cmd->post_wait_ms = p[4];
		cmd->msg.tx_len = get_unaligned_be16(p + 5);
		cmd->msg.tx_buf = p + 7;
		p += 7 + cmd->msg.tx_len;
	}
	if (expected) {
		snprintf(key, sizeof(key), "%s-update", prop);
		updates = of_get_property(node, key, &bytes);
		if (!updates)
			goto out_data;
		rc = m11a_update(&set, updates, bytes, expected, v);
		if (rc)
			goto out_data;
	}
	for (i = 0; i < set.count; i++) {
		struct dsi_cmd_desc *cmd = &set.cmds[i];

		if (started)
			*started = true;
		rc = dsi_host_transfer_sub(&d->host, cmd, false);
		if (rc < 0)
			goto out_data;
		if (atomic_read(&d->panel->esd_recovery_pending)) {
			rc = -EAGAIN;
			goto out_data;
		}
		if (cmd->post_wait_ms)
			usleep_range(cmd->post_wait_ms * 1000, cmd->post_wait_ms * 1000 + 100);
	}
	rc = m11a_host_ready(d);
out_data:
	kfree(data);
out_set:
	kfree(set.cmds);
out_node:
	of_node_put(node);
	return rc;
}

int m11a_send_capture(struct dsi_display *d, enum m11a_target target,
		      enum m11a_doze doze, u32 dbv, bool *started)
{
	struct m11a_values v = {};
	unsigned int expected = PATCH_RGB | PATCH_ALPHA;
	const char *prop;
	int rc;

	if (dbv > M11A_MAX_DBV)
		return -ERANGE;
	v.dbv = dbv;
	if (target == M11A_GREEN_500) {
		if (doze)
			return -EOPNOTSUPP;
		v.keep_green = true;
		prop = M11A_LHBM "normal-green-500nit-command";
	} else {
		rc = m11a_white_rgb(d, target, v.rgb);
		if (rc)
			return rc;
		if (target == M11A_WHITE_110)
			prop = doze ? M11A_LHBM "hlpm-white-110nit-command" :
				      M11A_LHBM "normal-white-110nit-command";
		else
			prop = doze ? M11A_LHBM "hlpm-white-1000nit-command" :
				      M11A_LHBM "normal-white-1000nit-command";
	}
	if (doze)
		expected |= PATCH_DBV;
	if (target != M11A_WHITE_110)
		expected |= PATCH_DF;
	return m11a_send(d, prop, expected, &v, started);
}

int m11a_send_release(struct dsi_display *d, enum m11a_doze doze, u32 dbv)
{
	struct m11a_values v = {};

	if (doze == M11A_DOZE_HIGH)
		return m11a_send(d, M11A_LHBM "off-to-hlpm-command", 0, NULL, NULL);
	if (doze == M11A_DOZE_LOW)
		return m11a_send(d, M11A_LHBM "off-to-llpm-command", 0, NULL, NULL);
	if (dbv > M11A_MAX_DBV)
		return -ERANGE;
	v.dbv = dbv;
	/* M11A global OFF-to-HBM and OFF-to-normal have identical packets. */
	return m11a_send(d, M11A_LHBM "off-to-normal-command", PATCH_DBV, &v, NULL);
}

int m11a_send_doze(struct dsi_display *d, enum m11a_doze doze)
{
	return m11a_send(d, doze == M11A_DOZE_HIGH ? "mi,mdss-dsi-doze-hbm-command" :
			  "mi,mdss-dsi-doze-lbm-command", 0, NULL, NULL);
}

int m11a_send_nolp(struct dsi_display *d, u32 dbv)
{
	struct m11a_values v = {};

	if (dbv > M11A_MAX_DBV)
		return -ERANGE;
	v.dbv = dbv;
	return m11a_send(d, "qcom,mdss-dsi-nolp-command", PATCH_DBV, &v, NULL);
}
