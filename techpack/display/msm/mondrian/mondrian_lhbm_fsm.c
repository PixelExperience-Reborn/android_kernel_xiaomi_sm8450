// SPDX-License-Identifier: GPL-2.0-only
/*
 * mondrian-only LHBM state-machine core. The hardware consumer intentionally
 * does not exist yet: do not guess Xiaomi DCS or manufacture FOD-ready events.
 * All calls must be serialized by the eventual owner of the panel lock.
 */
#include "mondrian_lhbm_fsm.h"
#ifdef MONDRIAN_LHBM_HOST_TEST
#include <errno.h>
#else
#include <linux/errno.h>
#endif

static int prepare(struct mondrian_lhbm_fsm *fsm,
		   struct mondrian_lhbm_effect *effect)
{
	if (!fsm || !effect)
		return -EINVAL;
	effect->hw = MONDRIAN_LHBM_HW_NONE;
	effect->token = fsm->token;
	effect->signal_fod_ready = false;
	effect->fod_ready = false;
	return 0;
}

static int next_token(struct mondrian_lhbm_fsm *fsm,
		      struct mondrian_lhbm_effect *effect)
{
	/* Wrapped tokens could accept an old asynchronous hardware ACK. */
	if (fsm->token == ~0U) {
		fsm->phase = MONDRIAN_LHBM_FAULT;
		return -EOVERFLOW;
	}
	fsm->token++;
	effect->token = fsm->token;
	return 0;
}

static int request_stop(struct mondrian_lhbm_fsm *fsm,
			struct mondrian_lhbm_effect *effect)
{
	int rc = next_token(fsm, effect);
	if (rc)
		return rc;
	fsm->phase = MONDRIAN_LHBM_STOPPING;
	effect->hw = MONDRIAN_LHBM_HW_OFF;
	return 0;
}

void mondrian_lhbm_init(struct mondrian_lhbm_fsm *fsm,
		       bool factory_qualified)
{
	if (!fsm)
		return;
	fsm->phase = MONDRIAN_LHBM_DISABLED;
	fsm->token = 1;
	fsm->panel_on = false;
	fsm->doze = false;
	fsm->esd = false;
	fsm->factory_qualified = factory_qualified;
	fsm->cancel_pending = false;
}

int mondrian_lhbm_panel_event(struct mondrian_lhbm_fsm *fsm,
			     enum mondrian_lhbm_panel_event event,
			     struct mondrian_lhbm_effect *effect)
{
	int rc = prepare(fsm, effect);
	if (rc)
		return rc;

	switch (event) {
	case MONDRIAN_LHBM_PANEL_ON:
		if (fsm->esd || fsm->phase == MONDRIAN_LHBM_FAULT)
			return -EAGAIN; /* Full OFF -> ON cycle required. */
		if (fsm->phase == MONDRIAN_LHBM_STOPPING ||
		    (fsm->panel_on && fsm->doze))
			return -EBUSY; /* A duplicate ON cannot bypass Doze. */
		fsm->panel_on = true;
		fsm->doze = false;
		if (!fsm->factory_qualified)
			return -EOPNOTSUPP;
		if (fsm->phase == MONDRIAN_LHBM_DISABLED)
			fsm->phase = MONDRIAN_LHBM_IDLE;
		return 0;
	case MONDRIAN_LHBM_PANEL_OFF:
	case MONDRIAN_LHBM_ESD_DETECTED:
		/* Never attempt DSI after power loss or during ESD recovery. */
		if (fsm->phase == MONDRIAN_LHBM_READY)
			effect->signal_fod_ready = true;
		fsm->panel_on = false;
		fsm->doze = false;
		fsm->esd = event == MONDRIAN_LHBM_ESD_DETECTED;
		fsm->cancel_pending = false;
		fsm->phase = MONDRIAN_LHBM_DISABLED;
		return next_token(fsm, effect);
	case MONDRIAN_LHBM_DOZE_ENTER:
		if (!fsm->panel_on)
			return -ENODEV;
		fsm->doze = true;
		if (fsm->phase == MONDRIAN_LHBM_READY) {
			effect->signal_fod_ready = true;
			return request_stop(fsm, effect);
		}
		if (fsm->phase == MONDRIAN_LHBM_STARTING) {
			/* Preserve in-flight ON order; dispatch OFF after its ACK. */
			fsm->cancel_pending = true;
			return 0;
		}
		if (fsm->phase == MONDRIAN_LHBM_IDLE)
			fsm->phase = MONDRIAN_LHBM_DISABLED;
		return 0;
	case MONDRIAN_LHBM_DOZE_EXIT:
		if (!fsm->panel_on || fsm->esd)
			return -ENODEV;
		if (fsm->phase == MONDRIAN_LHBM_FAULT)
			return -EIO;
		if (fsm->phase == MONDRIAN_LHBM_STOPPING)
			return -EBUSY;
		fsm->doze = false;
		if (fsm->factory_qualified &&
		    fsm->phase == MONDRIAN_LHBM_DISABLED)
			fsm->phase = MONDRIAN_LHBM_IDLE;
		return fsm->factory_qualified ? 0 : -EOPNOTSUPP;
	}
	return -EINVAL;
}

int mondrian_lhbm_finger(struct mondrian_lhbm_fsm *fsm, bool down,
			struct mondrian_lhbm_effect *effect)
{
	int rc = prepare(fsm, effect);
	if (rc)
		return rc;

	if (!down) {
		if (fsm->phase == MONDRIAN_LHBM_STARTING) {
			/* Do not put OFF ahead of an asynchronous ON operation. */
			fsm->cancel_pending = true;
			return 0;
		}
		if (fsm->phase == MONDRIAN_LHBM_READY) {
			effect->signal_fod_ready = true;
			return request_stop(fsm, effect);
		}
		return 0;
	}
	if (!fsm->factory_qualified)
		return -EOPNOTSUPP;
	if (!fsm->panel_on || fsm->doze || fsm->esd)
		return -EAGAIN;
	if (fsm->phase == MONDRIAN_LHBM_FAULT)
		return -EIO;
	if (fsm->phase == MONDRIAN_LHBM_STOPPING)
		return -EBUSY;
	if (fsm->phase == MONDRIAN_LHBM_STARTING)
		return fsm->cancel_pending ? -EBUSY : 0;
	if (fsm->phase == MONDRIAN_LHBM_READY)
		return 0; /* Duplicate DOWN must not retransmit. */
	if (fsm->phase != MONDRIAN_LHBM_IDLE)
		return -EAGAIN;
	rc = next_token(fsm, effect);
	if (rc)
		return rc;
	fsm->phase = MONDRIAN_LHBM_STARTING;
	effect->hw = MONDRIAN_LHBM_HW_ON;
	return 0;
}

int mondrian_lhbm_complete(struct mondrian_lhbm_fsm *fsm, bool on,
			  bool success, unsigned int token,
			  struct mondrian_lhbm_effect *effect)
{
	int rc = prepare(fsm, effect);
	if (rc)
		return rc;
	if (token != fsm->token)
		return -ESTALE;
	if (on) {
		if (fsm->phase != MONDRIAN_LHBM_STARTING)
			return -ESTALE;
		if (!success || fsm->cancel_pending || !fsm->panel_on ||
		    fsm->doze || fsm->esd || !fsm->factory_qualified) {
			/* Physical ON completed before we may safely queue OFF. */
			fsm->cancel_pending = false;
			return request_stop(fsm, effect);
		}
		fsm->phase = MONDRIAN_LHBM_READY;
		effect->signal_fod_ready = true;
		effect->fod_ready = true; /* Real hardware ON ACK is mandatory. */
		return 0;
	}
	if (fsm->phase != MONDRIAN_LHBM_STOPPING)
		return -ESTALE;
	if (!success) {
		fsm->phase = MONDRIAN_LHBM_FAULT;
		return -EIO; /* Requires a full panel power cycle. */
	}
	fsm->cancel_pending = false;
	fsm->phase = (fsm->panel_on && !fsm->doze && !fsm->esd &&
		      fsm->factory_qualified) ?
		MONDRIAN_LHBM_IDLE : MONDRIAN_LHBM_DISABLED;
	return 0;
}

int mondrian_lhbm_timeout(struct mondrian_lhbm_fsm *fsm,
			 unsigned int token, struct mondrian_lhbm_effect *effect)
{
	int rc = prepare(fsm, effect);
	if (rc)
		return rc;
	if (token != fsm->token)
		return -ESTALE;
	if (fsm->phase == MONDRIAN_LHBM_STARTING) {
		/* Hardware ON may still be in-flight. An OFF here can race it.
		 * Demand a complete panel reset rather than send unsafe DSI.
		 */
		fsm->cancel_pending = false;
		fsm->phase = MONDRIAN_LHBM_FAULT;
		return -ETIMEDOUT;
	}
	if (fsm->phase == MONDRIAN_LHBM_STOPPING) {
		fsm->phase = MONDRIAN_LHBM_FAULT;
		return -ETIMEDOUT;
	}
	return -EINVAL;
}
