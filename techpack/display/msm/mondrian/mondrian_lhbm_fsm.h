/* SPDX-License-Identifier: GPL-2.0-only */
/* Native mondrian-only LHBM/FOD state core. No device IO or UAPI. */
#ifndef _MONDRIAN_LHBM_FSM_H
#define _MONDRIAN_LHBM_FSM_H

#ifdef MONDRIAN_LHBM_HOST_TEST
#include <stdbool.h>
#else
#include <linux/types.h>
#endif

enum mondrian_lhbm_phase {
	MONDRIAN_LHBM_DISABLED,
	MONDRIAN_LHBM_IDLE,
	MONDRIAN_LHBM_STARTING,
	MONDRIAN_LHBM_READY,
	MONDRIAN_LHBM_STOPPING,
	MONDRIAN_LHBM_FAULT,
};

enum mondrian_lhbm_panel_event {
	MONDRIAN_LHBM_PANEL_ON,
	MONDRIAN_LHBM_PANEL_QUIESCE,
	MONDRIAN_LHBM_PANEL_OFF,
	MONDRIAN_LHBM_DOZE_ENTER,
	MONDRIAN_LHBM_DOZE_EXIT,
	MONDRIAN_LHBM_ESD_DETECTED,
};

enum mondrian_lhbm_hw_intent {
	MONDRIAN_LHBM_HW_NONE,
	MONDRIAN_LHBM_HW_ON,
	MONDRIAN_LHBM_HW_OFF,
};

/* The future panel owner must serialize calls under its panel lock. */
struct mondrian_lhbm_effect {
	enum mondrian_lhbm_hw_intent hw;
	unsigned int token;
	bool signal_fod_ready;
	bool fod_ready;
};

struct mondrian_lhbm_fsm {
	enum mondrian_lhbm_phase phase;
	unsigned int token;
	bool panel_on;
	bool doze;
	bool esd;
	bool factory_qualified;
	bool cancel_pending;
	/* Remains set until physical panel power-off is acknowledged. */
	bool power_off_pending;
};

void mondrian_lhbm_init(struct mondrian_lhbm_fsm *fsm, bool factory_qualified);
int mondrian_lhbm_panel_event(struct mondrian_lhbm_fsm *fsm,
	enum mondrian_lhbm_panel_event event, struct mondrian_lhbm_effect *effect);
int mondrian_lhbm_finger(struct mondrian_lhbm_fsm *fsm,
	bool down, struct mondrian_lhbm_effect *effect);
int mondrian_lhbm_complete(struct mondrian_lhbm_fsm *fsm, bool on,
	bool success, unsigned int token, struct mondrian_lhbm_effect *effect);
int mondrian_lhbm_timeout(struct mondrian_lhbm_fsm *fsm,
	unsigned int token, struct mondrian_lhbm_effect *effect);

#endif /* _MONDRIAN_LHBM_FSM_H */
