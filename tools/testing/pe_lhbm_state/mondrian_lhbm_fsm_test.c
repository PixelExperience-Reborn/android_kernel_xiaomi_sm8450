/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include "mondrian_lhbm_fsm.h"

static struct mondrian_lhbm_fsm state;
static struct mondrian_lhbm_effect effect;

static void ready_panel(void)
{
	mondrian_lhbm_init(&state, true);
	assert(mondrian_lhbm_panel_event(&state, MONDRIAN_LHBM_PANEL_ON,
					&effect) == 0);
	assert(state.phase == MONDRIAN_LHBM_IDLE);
}

static unsigned int turn_on(void)
{
	assert(mondrian_lhbm_finger(&state, true, &effect) == 0);
	assert(effect.hw == MONDRIAN_LHBM_HW_ON);
	assert(!effect.signal_fod_ready);
	assert(state.phase == MONDRIAN_LHBM_STARTING);
	return effect.token;
}

static void ack_on(unsigned int token)
{
	assert(mondrian_lhbm_complete(&state, true, true, token, &effect) == 0);
	assert(effect.hw == MONDRIAN_LHBM_HW_NONE);
	assert(effect.signal_fod_ready && effect.fod_ready);
	assert(state.phase == MONDRIAN_LHBM_READY);
}

static unsigned int turn_off(void)
{
	assert(mondrian_lhbm_finger(&state, false, &effect) == 0);
	assert(effect.signal_fod_ready && !effect.fod_ready);
	assert(effect.hw == MONDRIAN_LHBM_HW_OFF);
	assert(state.phase == MONDRIAN_LHBM_STOPPING);
	return effect.token;
}

static void test_unqualified_is_inert(void)
{
	mondrian_lhbm_init(&state, false);
	assert(mondrian_lhbm_panel_event(&state, MONDRIAN_LHBM_PANEL_ON,
					&effect) == -EOPNOTSUPP);
	assert(mondrian_lhbm_finger(&state, true, &effect) == -EOPNOTSUPP);
	assert(effect.hw == MONDRIAN_LHBM_HW_NONE);
	assert(!effect.signal_fod_ready);
	assert(state.phase == MONDRIAN_LHBM_DISABLED);
}

static void test_finger_cycle_and_duplicate_requests(void)
{
	unsigned int on, off;
	ready_panel();
	on = turn_on();
	assert(mondrian_lhbm_finger(&state, true, &effect) == 0);
	assert(effect.hw == MONDRIAN_LHBM_HW_NONE);
	ack_on(on);
	assert(mondrian_lhbm_finger(&state, true, &effect) == 0);
	assert(!effect.signal_fod_ready);
	off = turn_off();
	assert(mondrian_lhbm_complete(&state, false, true, off, &effect) == 0);
	assert(state.phase == MONDRIAN_LHBM_IDLE);
	assert(!effect.signal_fod_ready);
	assert(mondrian_lhbm_finger(&state, false, &effect) == 0);
	assert(effect.hw == MONDRIAN_LHBM_HW_NONE);
}

static void test_release_racing_with_on_completion(void)
{
	unsigned int on, off;
	ready_panel();
	on = turn_on();
	assert(mondrian_lhbm_finger(&state, false, &effect) == 0);
	assert(effect.hw == MONDRIAN_LHBM_HW_NONE);
	assert(state.cancel_pending);
	assert(!effect.signal_fod_ready);
	assert(mondrian_lhbm_finger(&state, true, &effect) == -EBUSY);
	/* Only the original hardware ON ACK can now release an OFF intent. */
	assert(mondrian_lhbm_complete(&state, true, true, on, &effect) == 0);
	assert(effect.hw == MONDRIAN_LHBM_HW_OFF);
	assert(!effect.signal_fod_ready);
	off = effect.token;
	assert(on != off);
	assert(mondrian_lhbm_complete(&state, true, true, on, &effect) == -ESTALE);
	assert(mondrian_lhbm_complete(&state, false, true, off, &effect) == 0);
	assert(state.phase == MONDRIAN_LHBM_IDLE);
}

static void test_doze_cancels_ready(void)
{
	unsigned int on, off;
	ready_panel();
	on = turn_on();
	ack_on(on);
	assert(mondrian_lhbm_panel_event(&state, MONDRIAN_LHBM_DOZE_ENTER,
					&effect) == 0);
	assert(effect.signal_fod_ready && !effect.fod_ready);
	assert(effect.hw == MONDRIAN_LHBM_HW_OFF);
	off = effect.token;
	assert(mondrian_lhbm_finger(&state, true, &effect) == -EAGAIN);
	assert(mondrian_lhbm_panel_event(&state, MONDRIAN_LHBM_DOZE_EXIT,
					&effect) == -EBUSY);
	assert(mondrian_lhbm_complete(&state, false, true, off, &effect) == 0);
	assert(state.phase == MONDRIAN_LHBM_DISABLED);
	assert(mondrian_lhbm_panel_event(&state, MONDRIAN_LHBM_DOZE_EXIT,
					&effect) == 0);
	assert(state.phase == MONDRIAN_LHBM_IDLE);
}

static void test_esd_requires_off_on_cycle(void)
{
	unsigned int on;
	ready_panel();
	on = turn_on();
	ack_on(on);
	assert(mondrian_lhbm_panel_event(&state, MONDRIAN_LHBM_ESD_DETECTED,
					&effect) == 0);
	assert(effect.signal_fod_ready && !effect.fod_ready);
	assert(effect.hw == MONDRIAN_LHBM_HW_NONE);
	assert(mondrian_lhbm_complete(&state, true, true, on, &effect) == -ESTALE);
	assert(mondrian_lhbm_panel_event(&state, MONDRIAN_LHBM_PANEL_ON,
					&effect) == -EAGAIN);
	assert(mondrian_lhbm_panel_event(&state, MONDRIAN_LHBM_PANEL_OFF,
					&effect) == 0);
	assert(mondrian_lhbm_panel_event(&state, MONDRIAN_LHBM_PANEL_ON,
					&effect) == 0);
}

static void test_panel_off_invalidates_late_ack(void)
{
	unsigned int on;
	ready_panel();
	on = turn_on();
	assert(mondrian_lhbm_panel_event(&state, MONDRIAN_LHBM_PANEL_OFF,
					&effect) == 0);
	assert(!effect.signal_fod_ready);
	assert(effect.hw == MONDRIAN_LHBM_HW_NONE);
	assert(mondrian_lhbm_complete(&state, true, true, on, &effect) == -ESTALE);
	assert(state.phase == MONDRIAN_LHBM_DISABLED);
}

static void test_timeouts_cannot_claim_ready(void)
{
	unsigned int on, off;
	ready_panel();
	on = turn_on();
	assert(mondrian_lhbm_timeout(&state, on, &effect) == -ETIMEDOUT);
	assert(effect.hw == MONDRIAN_LHBM_HW_NONE);
	assert(!effect.signal_fod_ready);
	assert(state.phase == MONDRIAN_LHBM_FAULT);
	assert(mondrian_lhbm_finger(&state, true, &effect) == -EIO);

	/* OFF can time out independently, without fabricating READY. */
	ready_panel();
	on = turn_on();
	ack_on(on);
	off = turn_off();
	assert(mondrian_lhbm_timeout(&state, off, &effect) == -ETIMEDOUT);
	assert(state.phase == MONDRIAN_LHBM_FAULT);
	assert(!effect.signal_fod_ready);
}

static void test_failed_on_forces_off_and_failed_off_is_sticky(void)
{
	unsigned int on;
	ready_panel();
	on = turn_on();
	assert(mondrian_lhbm_complete(&state, true, false, on, &effect) == 0);
	assert(effect.hw == MONDRIAN_LHBM_HW_OFF);
	assert(!effect.signal_fod_ready);
	assert(mondrian_lhbm_complete(&state, false, false, effect.token,
				     &effect) == -EIO);
	assert(state.phase == MONDRIAN_LHBM_FAULT);
}

static void test_wrong_completion_never_signals_ready(void)
{
	unsigned int on;
	ready_panel();
	on = turn_on();
	assert(mondrian_lhbm_complete(&state, false, true, on, &effect) == -ESTALE);
	assert(!effect.signal_fod_ready);
	assert(mondrian_lhbm_complete(&state, true, true, on + 1,
				     &effect) == -ESTALE);
	assert(!effect.signal_fod_ready);
	assert(state.phase == MONDRIAN_LHBM_STARTING);
}

static void test_generation_wrap_fails_closed(void)
{
	ready_panel();
	state.token = UINT_MAX;
	assert(mondrian_lhbm_finger(&state, true, &effect) == -EOVERFLOW);
	assert(state.phase == MONDRIAN_LHBM_FAULT);
	assert(effect.hw == MONDRIAN_LHBM_HW_NONE);
}

static void test_doze_while_on_pending_is_serialized(void)
{
	unsigned int on, off;
	ready_panel();
	on = turn_on();
	assert(mondrian_lhbm_panel_event(&state, MONDRIAN_LHBM_DOZE_ENTER,
					&effect) == 0);
	assert(state.cancel_pending);
	assert(effect.hw == MONDRIAN_LHBM_HW_NONE);
	assert(!effect.signal_fod_ready);
	assert(mondrian_lhbm_complete(&state, true, true, on, &effect) == 0);
	assert(effect.hw == MONDRIAN_LHBM_HW_OFF);
	assert(!effect.signal_fod_ready);
	off = effect.token;
	assert(mondrian_lhbm_complete(&state, false, true, off, &effect) == 0);
	assert(state.phase == MONDRIAN_LHBM_DISABLED);
}

static void test_duplicate_panel_on_cannot_escape_doze(void)
{
	ready_panel();
	assert(mondrian_lhbm_panel_event(&state, MONDRIAN_LHBM_DOZE_ENTER,
					&effect) == 0);
	assert(state.doze);
	assert(mondrian_lhbm_panel_event(&state, MONDRIAN_LHBM_PANEL_ON,
					&effect) == -EBUSY);
	assert(state.doze);
	assert(mondrian_lhbm_finger(&state, true, &effect) == -EAGAIN);
}

static void test_invalid_inputs(void)
{
	mondrian_lhbm_init(&state, true);
	assert(mondrian_lhbm_panel_event(NULL, MONDRIAN_LHBM_PANEL_ON,
					&effect) == -EINVAL);
	assert(mondrian_lhbm_finger(&state, true, NULL) == -EINVAL);
	assert(mondrian_lhbm_panel_event(&state, 99, &effect) == -EINVAL);
}

int main(void)
{
	test_unqualified_is_inert();
	test_finger_cycle_and_duplicate_requests();
	test_release_racing_with_on_completion();
	test_doze_cancels_ready();
	test_esd_requires_off_on_cycle();
	test_panel_off_invalidates_late_ack();
	test_timeouts_cannot_claim_ready();
	test_failed_on_forces_off_and_failed_off_is_sticky();
	test_wrong_completion_never_signals_ready();
	test_generation_wrap_fails_closed();
	test_doze_while_on_pending_is_serialized();
	test_duplicate_panel_on_cannot_escape_doze();
	test_invalid_inputs();
	puts("[PASS] 13 native mondrian LHBM/FOD cases (no DSI hardware IO)");
	return 0;
}
