/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _MONDRIAN_FOD_H
#define _MONDRIAN_FOD_H

#include <linux/types.h>
#include "mondrian_lhbm_fsm.h"

struct dsi_display;
struct dsi_panel;
struct mondrian_fod;

enum m11a_target {
	M11A_FINGER_UP, M11A_AUTH_STOP, M11A_WHITE_1000, M11A_WHITE_110,
	M11A_GREEN_500,
};

enum m11a_doze {
	M11A_NORMAL, M11A_DOZE_HIGH, M11A_DOZE_LOW,
};

void mondrian_fod_attach(struct dsi_display *display);
void mondrian_fod_detach(struct dsi_display *display);
void mondrian_fod_event_locked(struct dsi_panel *panel,
			       enum mondrian_lhbm_panel_event event);
int mondrian_fod_stop_locked(struct dsi_panel *panel);
int mondrian_fod_nolp_locked(struct dsi_panel *panel, bool *handled);
bool mondrian_fod_defer_bl_locked(struct dsi_panel *panel, u32 level);
void mondrian_fod_applied_bl_locked(struct dsi_panel *panel, u32 level);

int m11a_host_ready(struct dsi_display *display);
int m11a_dcs_read_locked(struct dsi_display *display, u8 reg, void *buf, size_t len);
int m11a_send_capture(struct dsi_display *display, enum m11a_target target,
		      enum m11a_doze doze, u32 dbv, bool *started);
int m11a_send_release(struct dsi_display *display, enum m11a_doze doze, u32 dbv);
int m11a_send_nolp(struct dsi_display *display, u32 dbv);
int m11a_send_doze(struct dsi_display *display, enum m11a_doze doze);

#endif
