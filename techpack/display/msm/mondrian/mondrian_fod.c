// SPDX-License-Identifier: GPL-2.0-only
/* Primary mondrian display. Wire layout follows Xiaomi mi_disp.h. */
#include <linux/compat.h>
#include <linux/fs.h>
#include <linux/kref.h>
#include <linux/cdev.h>
#include <linux/device.h>
#include <linux/of.h>
#include <linux/poll.h>
#include <linux/slab.h>
#include <linux/uaccess.h>
#include <linux/workqueue.h>
#include <video/mipi_display.h>
#include <asm/unaligned.h>
#include "../dsi/dsi_display.h"
#include "mondrian_fod.h"

struct mi_fod_req { __u32 flags, display, value; };
struct mi_fod_event { __s32 display; __u32 type, length, value; };
#define MI_SET_DOZE       _IOW('D', 0x02, struct mi_fod_req)
#define MI_REGISTER       _IOW('D', 0x07, struct mi_fod_req)
#define MI_DEREGISTER     _IOW('D', 0x08, struct mi_fod_req)
#define MI_SET_LOCAL_HBM  _IOW('D', 0x0e, struct mi_fod_req)
#define MI_FOD_EVENT 2
#define MI_FOD_READY BIT(3)
#define MI_FOD_LOW BIT(2)

struct mondrian_fod {
	struct class *class;
	struct cdev *cdev;
	dev_t devt;
	struct kref refs;
	struct rw_semaphore live;
	struct dsi_display *display;
	struct delayed_work ready_work;
	/* The panel lock protects all fields from 'doze' through 'owner'. */
	enum m11a_doze doze;
	enum m11a_target target;
	u32 frames, rate, token, dbv, doze_dbv[3];
	bool known_dbv;
	ktime_t ready_at;
	struct m11a_client *owner;
	spinlock_t events;
	wait_queue_head_t wait;
	u64 sequence;
	u32 value;
	bool dead;
};

struct m11a_client {
	struct mondrian_fod *fod;
	struct mutex read_lock;
	u64 seen, registration, partial_seq;
	u32 partial_value;
	size_t offset;
	bool subscribed;
};

/* A retained inode can outlive a reprobe. Match the active cdev under this lock. */
static DEFINE_MUTEX(registry_lock);
static struct mondrian_fod *primary;

static void fod_free(struct kref *ref)
{
	kfree(container_of(ref, struct mondrian_fod, refs));
}

static void publish(struct mondrian_fod *f, u32 value)
{
	spin_lock(&f->events);
	if (f->value != value) {
		f->value = value;
		f->sequence++;
	}
	spin_unlock(&f->events);
	wake_up_interruptible(&f->wait);
}

static int release_light(struct mondrian_fod *f, struct mondrian_lhbm_effect *e)
{
	struct mondrian_lhbm_fsm *fsm = &f->display->panel->mondrian_lhbm;
	int rc, ack;

	f->owner = NULL;
	publish(f, 0);
	rc = m11a_send_release(f->display, f->doze, f->dbv);
	ack = mondrian_lhbm_complete(fsm, false, !rc, e->token, e);
	return rc ? rc : ack;
}

int mondrian_fod_stop_locked(struct dsi_panel *panel)
{
	struct mondrian_fod *f = panel->mondrian_fod;
	struct mondrian_lhbm_fsm *fsm = &panel->mondrian_lhbm;
	struct mondrian_lhbm_effect e;
	int rc;

	if (!f || !f->owner)
		return 0;
	cancel_delayed_work(&f->ready_work);
	rc = mondrian_lhbm_finger(fsm, false, &e);
	if (!rc && fsm->phase == MONDRIAN_LHBM_STARTING) {
		/* TX already returned under this lock; only the optical delay remains. */
		rc = mondrian_lhbm_complete(fsm, true, false, e.token, &e);
	}
	if (rc || e.hw != MONDRIAN_LHBM_HW_OFF) {
		f->owner = NULL;
		fsm->phase = MONDRIAN_LHBM_FAULT;
		publish(f, 0);
		return rc ? rc : -EIO;
	}
	return release_light(f, &e);
}

int mondrian_fod_nolp_locked(struct dsi_panel *panel, bool *handled)
{
	struct mondrian_fod *f = panel->mondrian_fod;

	*handled = f && f->doze && f->known_dbv;
	return *handled ? m11a_send_nolp(f->display, f->dbv) : 0;
}

bool mondrian_fod_defer_bl_locked(struct dsi_panel *panel, u32 level)
{
	struct mondrian_fod *f = panel->mondrian_fod;

	if (!f || !f->owner)
		return false;
	if (!panel->mondrian_lhbm.doze) {
		f->dbv = level;
		f->known_dbv = true;
	}
	return true;
}

void mondrian_fod_applied_bl_locked(struct dsi_panel *panel, u32 level)
{
	struct mondrian_fod *f = panel->mondrian_fod;

	if (f && !panel->mondrian_lhbm.doze && level <= 4095) {
		f->dbv = level;
		f->known_dbv = true;
	}
}

void mondrian_fod_event_locked(struct dsi_panel *panel, enum mondrian_lhbm_panel_event event)
{
	struct mondrian_fod *f = panel->mondrian_fod;
	struct mondrian_lhbm_effect e;

	if (event == MONDRIAN_LHBM_PANEL_QUIESCE || event == MONDRIAN_LHBM_PANEL_OFF ||
	    event == MONDRIAN_LHBM_ESD_DETECTED || event == MONDRIAN_LHBM_DOZE_EXIT) {
		cancel_delayed_work(&f->ready_work);
		f->owner = NULL;
		f->doze = M11A_NORMAL;
		panel->mondrian_lhbm.doze_capture = false;
		if (event != MONDRIAN_LHBM_DOZE_EXIT)
			f->known_dbv = false;
		publish(f, 0);
	}
	mondrian_lhbm_panel_event(&panel->mondrian_lhbm, event, &e);
}

static void ready_worker(struct work_struct *work)
{
	struct mondrian_fod *f = container_of(to_delayed_work(work), struct mondrian_fod, ready_work);
	struct dsi_display *d = f->display;
	struct dsi_panel *p = d->panel;
	struct mondrian_lhbm_fsm *fsm = &p->mondrian_lhbm;
	struct mondrian_lhbm_effect e;
	s64 left;
	int rc;

	mutex_lock(&d->display_lock);
	mutex_lock(&p->panel_lock);
	if (READ_ONCE(f->dead) || !f->owner || f->token != fsm->token ||
	    fsm->phase != MONDRIAN_LHBM_STARTING)
		goto out;
	left = ktime_us_delta(f->ready_at, ktime_get());
	if (left > 0) {
		mod_delayed_work(system_wq, &f->ready_work, max_t(unsigned long, 1, usecs_to_jiffies(left)));
		goto out;
	}
	if (m11a_host_ready(d) || !p->cur_mode || f->rate != p->cur_mode->timing.refresh_rate) {
		mondrian_fod_stop_locked(p);
		goto out;
	}
	rc = mondrian_lhbm_complete(fsm, true, true, f->token, &e);
	if (!rc && e.hw == MONDRIAN_LHBM_HW_OFF)
		release_light(f, &e);
	else if (!rc && e.signal_fod_ready && e.fod_ready)
		publish(f, MI_FOD_READY | (f->target == M11A_WHITE_110 ? MI_FOD_LOW : 0));
out:
	mutex_unlock(&p->panel_lock);
	mutex_unlock(&d->display_lock);
}

/* Splash hand-off can omit the ordinary panel-enable callback. Read the panel
 * before accepting that transition and preserve the physical-off / ESD latch.
 */
static int sync_panel(struct mondrian_fod *f)
{
	struct dsi_display *d = f->display;
	struct mondrian_lhbm_fsm *fsm = &d->panel->mondrian_lhbm;
	struct mondrian_lhbm_effect e;
	const u8 on = MIPI_DSI_DCS_POWER_MODE_DISPLAY | MIPI_DSI_DCS_POWER_MODE_SLEEP;
	u8 status;
	int rc = m11a_host_ready(d);

	if (rc || fsm->esd || fsm->power_off_pending || fsm->phase == MONDRIAN_LHBM_FAULT)
		return rc ? rc : -EIO;
	if (fsm->panel_on && (fsm->phase != MONDRIAN_LHBM_DISABLED || fsm->doze))
		return 0;
	rc = m11a_dcs_read_locked(d, MIPI_DCS_GET_POWER_MODE, &status, 1);
	if (rc || (status & on) != on)
		return rc ? rc : -EAGAIN;
	return mondrian_lhbm_panel_event(fsm, MONDRIAN_LHBM_PANEL_ON, &e);
}

static int set_target(struct m11a_client *client, u32 target)
{
	struct mondrian_fod *f = client->fod;
	struct dsi_display *d = f->display;
	struct dsi_panel *p = d->panel;
	struct mondrian_lhbm_fsm *fsm = &p->mondrian_lhbm;
	struct mondrian_lhbm_effect e;
	bool started = false;
	u32 delay, level, hz;
	u8 data[2];
	int rc;

	if (target > M11A_GREEN_500)
		return -EINVAL;
	if (target <= M11A_AUTH_STOP)
		return mondrian_fod_stop_locked(p);
	if (f->owner)
		return f->owner == client && f->target == target ? 0 : -EBUSY;
	rc = sync_panel(f);
	if (rc || !p->cur_mode)
		return rc ? rc : -EAGAIN;
	hz = p->cur_mode->timing.refresh_rate;
	if (hz != 60 && hz != 90 && hz != 120)
		return -EOPNOTSUPP;
	if (fsm->doze && !f->doze)
		return -EAGAIN;
	if (!f->doze && !f->known_dbv) {
		rc = m11a_dcs_read_locked(d, MIPI_DCS_GET_DISPLAY_BRIGHTNESS, data, sizeof(data));
		if (rc)
			return rc;
		f->dbv = get_unaligned_be16(data);
		if (f->dbv > 4095)
			return -ERANGE;
		f->known_dbv = true;
	}
	level = f->doze ? f->doze_dbv[f->doze] : f->dbv;
	rc = mondrian_lhbm_finger(fsm, true, &e);
	if (rc || e.hw != MONDRIAN_LHBM_HW_ON)
		return rc ? rc : -EAGAIN;
	rc = m11a_send_capture(d, target, f->doze, level, &started);
	if (rc) {
		mondrian_lhbm_complete(fsm, true, false, e.token, &e);
		if (e.hw == MONDRIAN_LHBM_HW_OFF) {
			if (started)
				release_light(f, &e);
			else
				mondrian_lhbm_complete(fsm, false, true, e.token, &e);
		}
		return rc;
	}
	f->target = target;
	f->owner = client;
	f->rate = hz;
	f->token = e.token;
	delay = DIV_ROUND_UP(f->frames * USEC_PER_SEC, hz);
	f->ready_at = ktime_add_us(ktime_get(), delay);
	mod_delayed_work(system_wq, &f->ready_work, usecs_to_jiffies(delay));
	return 0;
}

static int set_doze(struct mondrian_fod *f, u32 level)
{
	struct dsi_panel *p = f->display->panel;
	struct mondrian_lhbm_fsm *fsm = &p->mondrian_lhbm;
	int rc;

	if (level > M11A_DOZE_LOW)
		return -EINVAL;
	if (f->owner) {
		rc = mondrian_fod_stop_locked(p);
		if (rc)
			return rc;
	}
	/* DRM NOLP owns the transition back to normal. */
	if (level == M11A_NORMAL)
		return 0;
	rc = sync_panel(f);
	if (rc)
		return rc;
	rc = m11a_send_doze(f->display, level);
	if (!rc) {
		struct mondrian_lhbm_effect e;

		if (!fsm->doze)
			mondrian_lhbm_panel_event(fsm, MONDRIAN_LHBM_DOZE_ENTER, &e);
		f->doze = level;
		fsm->doze_capture = true;
		if (fsm->phase == MONDRIAN_LHBM_DISABLED)
			fsm->phase = MONDRIAN_LHBM_IDLE;
	}
	return rc;
}

static long fod_ioctl(struct file *file, unsigned int cmd, unsigned long arg)
{
	struct m11a_client *c = file->private_data;
	struct mondrian_fod *f = c->fod;
	struct mi_fod_req req;
	struct dsi_display *d;
	int rc = 0;

	if (cmd != MI_REGISTER && cmd != MI_DEREGISTER && cmd != MI_SET_DOZE && cmd != MI_SET_LOCAL_HBM)
		return -ENOTTY;
	if (copy_from_user(&req, (void __user *)arg, sizeof(req)))
		return -EFAULT;
	if (req.display || req.flags > 1)
		return -EINVAL;
	down_read(&f->live);
	d = f->display;
	if (!d) {
		rc = -ENODEV;
	} else if (cmd == MI_REGISTER || cmd == MI_DEREGISTER) {
		if (req.value != MI_FOD_EVENT) {
			rc = -EOPNOTSUPP;
		} else {
			spin_lock(&f->events);
			c->subscribed = cmd == MI_REGISTER;
			c->registration++;
			c->offset = 0;
			c->seen = f->sequence - (c->subscribed && f->value ? 1 : 0);
			spin_unlock(&f->events);
			wake_up_interruptible(&f->wait);
		}
	} else {
		if (!(file->f_mode & FMODE_WRITE)) {
			rc = -EBADF;
			goto done;
		}
		mutex_lock(&d->display_lock);
		mutex_lock(&d->panel->panel_lock);
		rc = cmd == MI_SET_DOZE ? set_doze(f, req.value) : set_target(c, req.value);
		mutex_unlock(&d->panel->panel_lock);
		mutex_unlock(&d->display_lock);
	}
done:
	up_read(&f->live);
	return rc;
}

static __poll_t event_state(struct m11a_client *c)
{
	struct mondrian_fod *f = c->fod;
	__poll_t mask = 0;

	spin_lock(&f->events);
	if (f->dead)
		mask = EPOLLHUP | EPOLLERR;
	else if (c->subscribed && (c->offset || c->seen != f->sequence))
		mask = EPOLLIN | EPOLLRDNORM;
	spin_unlock(&f->events);
	return mask;
}

static __poll_t fod_poll(struct file *file, poll_table *wait)
{
	struct m11a_client *c = file->private_data;

	poll_wait(file, &c->fod->wait, wait);
	return event_state(c);
}

static ssize_t fod_read(struct file *file, char __user *buf, size_t len, loff_t *offset)
{
	struct m11a_client *c = file->private_data;
	struct mondrian_fod *f = c->fod;
	struct mi_fod_event e = { .type = MI_FOD_EVENT, .length = sizeof(e) };
	u64 seq, registration;
	size_t pos, size;
	int rc;

	if (!len)
		return 0;
	if (mutex_lock_interruptible(&c->read_lock))
		return -ERESTARTSYS;
	for (;;) {
		spin_lock(&f->events);
		if (f->dead || !c->subscribed) {
			rc = f->dead ? -ENODEV : -EINVAL;
			spin_unlock(&f->events);
			goto out;
		}
		pos = c->offset;
		registration = c->registration;
		seq = f->sequence;
		e.value = f->value;
		/* The 12-byte header is identical for every FOD event. Until
		 * the first payload byte is read, OFF can supersede READY.
		 * Once payload delivery starts, finish the same 32-bit value.
		 */
		if (pos > offsetof(struct mi_fod_event, value)) {
			seq = c->partial_seq;
			e.value = c->partial_value;
		}
		if (pos || c->seen != seq) {
			spin_unlock(&f->events);
			break;
		}
		spin_unlock(&f->events);
		if (file->f_flags & O_NONBLOCK) {
			rc = -EAGAIN;
			goto out;
		}
		rc = wait_event_interruptible(f->wait, event_state(c) || !READ_ONCE(c->subscribed));
		if (rc)
			goto out;
	}
	size = min(len, sizeof(e) - pos);
	rc = -EFAULT;
	if (!copy_to_user(buf, (u8 *)&e + pos, size)) {
		spin_lock(&f->events);
		/* A new subscription can start while copy_to_user sleeps. */
		if (registration == c->registration) {
			c->offset = pos + size;
			c->partial_seq = seq;
			c->partial_value = e.value;
			if (c->offset == sizeof(e)) {
				c->offset = 0;
				c->seen = seq;
			}
		}
		spin_unlock(&f->events);
		rc = size;
	}
out:
	mutex_unlock(&c->read_lock);
	return rc;
}

static int fod_open(struct inode *inode, struct file *file)
{
	struct mondrian_fod *f;
	struct m11a_client *c = kzalloc(sizeof(*c), GFP_KERNEL);

	if (!c)
		return -ENOMEM;
	mutex_lock(&registry_lock);
	f = primary;
	if (!f || f->cdev != inode->i_cdev) {
		mutex_unlock(&registry_lock);
		kfree(c);
		return -ENODEV;
	}
	kref_get(&f->refs);
	mutex_unlock(&registry_lock);
	mutex_init(&c->read_lock);
	c->fod = f;
	file->private_data = c;
	return nonseekable_open(inode, file);
}

static int fod_close(struct inode *inode, struct file *file)
{
	struct m11a_client *c = file->private_data;
	struct mondrian_fod *f = c->fod;
	struct dsi_display *d;

	down_read(&f->live);
	d = f->display;
	if (d) {
		mutex_lock(&d->display_lock);
		mutex_lock(&d->panel->panel_lock);
		if (f->owner == c)
			mondrian_fod_stop_locked(d->panel);
		mutex_unlock(&d->panel->panel_lock);
		mutex_unlock(&d->display_lock);
	}
	up_read(&f->live);
	kref_put(&f->refs, fod_free);
	kfree(c);
	return 0;
}

static const struct file_operations fod_fops = {
	.owner = THIS_MODULE, .open = fod_open, .release = fod_close,
	.unlocked_ioctl = fod_ioctl,
#ifdef CONFIG_COMPAT
	.compat_ioctl = compat_ptr_ioctl,
#endif
	.read = fod_read, .poll = fod_poll, .llseek = no_llseek,
};

static char *fod_devnode(struct device *dev, umode_t *mode)
{
	return kasprintf(GFP_KERNEL, "mi_display/%s", dev_name(dev));
}

void mondrian_fod_attach(struct dsi_display *d)
{
	struct dsi_panel *p = d->panel;
	struct device_node *np = p->panel_of_node;
	struct mondrian_fod *f;
	struct device *dev;
	u64 id;
	u32 frames;
	int rc;

	if (strcmp(d->display_type, "primary") || p->has_drm_panel || p->host_config.ext_bridge_mode ||
	    !of_property_read_bool(np, "xiaomi,mondrian-m11a-fod") ||
	    !of_property_read_bool(np, "mi,local-hbm-enabled") ||
	    of_property_read_u64(np, "mi,panel-id", &id) || id != 0x4d31314100420200ULL ||
	    of_property_read_u32(np, "mi,local-hbm-ui-ready-delay-num-frame", &frames) || frames != 4)
		return;
	f = kzalloc(sizeof(*f), GFP_KERNEL);
	if (!f)
		return;
	if (of_property_read_u32(np, "mi,doze-hbm-dbv-level", &f->doze_dbv[M11A_DOZE_HIGH]) ||
	    of_property_read_u32(np, "mi,doze-lbm-dbv-level", &f->doze_dbv[M11A_DOZE_LOW]) ||
	    f->doze_dbv[M11A_DOZE_LOW] > f->doze_dbv[M11A_DOZE_HIGH] ||
	    f->doze_dbv[M11A_DOZE_HIGH] > 4095) {
		kfree(f);
		return;
	}
	kref_init(&f->refs);
	init_rwsem(&f->live);
	init_waitqueue_head(&f->wait);
	spin_lock_init(&f->events);
	INIT_DELAYED_WORK(&f->ready_work, ready_worker);
	f->display = d;
	f->frames = frames;
	/* Android ueventd selects the stock /dev/mi_display directory by subsystem. */
	f->class = class_create(THIS_MODULE, "mi_display");
	if (IS_ERR(f->class)) {
		rc = PTR_ERR(f->class);
		goto free;
	}
	f->class->devnode = fod_devnode;
	rc = alloc_chrdev_region(&f->devt, 0, 1, "disp_feature");
	if (rc)
		goto destroy_class;
	f->cdev = cdev_alloc();
	if (!f->cdev) {
		rc = -ENOMEM;
		goto unregister;
	}
	f->cdev->ops = &fod_fops;
	f->cdev->owner = THIS_MODULE;
	rc = cdev_add(f->cdev, f->devt, 1);
	if (rc) {
		kobject_put(&f->cdev->kobj);
		goto unregister;
	}
	mutex_lock(&registry_lock);
	dev = device_create(f->class, NULL, f->devt, f, "disp_feature");
	if (IS_ERR(dev)) {
		mutex_unlock(&registry_lock);
		rc = PTR_ERR(dev);
		cdev_del(f->cdev);
		goto unregister;
	}
	mutex_lock(&p->panel_lock);
	p->mondrian_fod = f;
	p->mondrian_lhbm.factory_qualified = true;
	mutex_unlock(&p->panel_lock);
	primary = f;
	mutex_unlock(&registry_lock);
	return;

unregister:
	unregister_chrdev_region(f->devt, 1);
destroy_class:
	class_destroy(f->class);
free:
	dev_err(&d->pdev->dev, "M11A fingerprint display registration failed: %d\n", rc);
	kfree(f);
}

void mondrian_fod_detach(struct dsi_display *d)
{
	struct dsi_panel *p = d->panel;
	struct mondrian_fod *f = p ? p->mondrian_fod : NULL;

	if (!f)
		return;
	mutex_lock(&registry_lock);
	primary = NULL;
	mutex_unlock(&registry_lock);
	device_destroy(f->class, f->devt);
	cdev_del(f->cdev);
	unregister_chrdev_region(f->devt, 1);
	class_destroy(f->class);
	down_write(&f->live);
	spin_lock(&f->events);
	WRITE_ONCE(f->dead, true);
	spin_unlock(&f->events);
	wake_up_interruptible(&f->wait);
	cancel_delayed_work_sync(&f->ready_work);
	mutex_lock(&d->display_lock);
	mutex_lock(&p->panel_lock);
	mondrian_fod_stop_locked(p);
	p->mondrian_fod = NULL;
	mondrian_lhbm_init(&p->mondrian_lhbm, false);
	mutex_unlock(&p->panel_lock);
	mutex_unlock(&d->display_lock);
	f->display = NULL;
	up_write(&f->live);
	kref_put(&f->refs, fod_free);
}
