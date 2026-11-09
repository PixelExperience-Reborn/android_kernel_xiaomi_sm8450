/* SPDX-License-Identifier: GPL-2.0-only */
/*
 * Copyright (c) Qualcomm Innovation Center, Inc. and/or its subsidiaries.
 */

#ifndef __QCOM_DISPLAY_INTERNAL_H__
#define __QCOM_DISPLAY_INTERNAL_H__

#include <linux/types.h>
#include <linux/notifier.h>
#include <linux/soc/qcom/llcc-qcom.h>
#include <linux/errno.h>
#include <linux/of.h>

#define MMRM_CLIENT_DATA_FLAG_RESERVE_ONLY  0x0001
#define MMRM_CLK_CLIENT_NAME_SIZE  128
#define PFN_DEV (1ULL << (BITS_PER_LONG_LONG - 3))
#define DMA_ATTR_DELAYED_UNMAP      (1UL << 17)
#define DMA_ATTR_QTI_SMMU_PROXY_MAP (1UL << 18)

enum sid_switch_direction {
	SID_ACQUIRE,
	SID_RELEASE,
};

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

enum branch_mem_flags {
	CLKFLAG_RETAIN_PERIPH,
	CLKFLAG_NORETAIN_PERIPH,
	CLKFLAG_RETAIN_MEM,
	CLKFLAG_NORETAIN_MEM,
	CLKFLAG_PERIPH_OFF_SET,
	CLKFLAG_PERIPH_OFF_CLEAR,
};

enum mmrm_cb_type {
	MMRM_CLIENT_RESOURCE_VALUE_CHANGE = 0x1,
};

enum mmrm_client_priority {
	MMRM_CLIENT_PRIOR_HIGH = 0x1,
	MMRM_CLIENT_PRIOR_LOW  = 0x2
};
enum mmrm_client_domain {
	MMRM_CLIENT_DOMAIN_CAMERA = 0x1,
	MMRM_CLIENT_DOMAIN_CVP = 0x2,
	MMRM_CLIENT_DOMAIN_DISPLAY = 0x3,
	MMRM_CLIENT_DOMAIN_VIDEO = 0x4,
};

enum mmrm_client_type {
	MMRM_CLIENT_CLOCK,
};

enum mmrm_crm_drv_type {
	MMRM_CRM_SW_DRV,
	MMRM_CRM_HW_DRV,
};

struct mmrm_client_data {
	u32 num_hw_blocks;
	u32 flags;

	/* CESTA data */
	enum mmrm_crm_drv_type drv_type;
	u32 crm_drv_idx;
	u32 pwr_st;
};

struct mmrm_res_val_chng {
	unsigned long old_val;
	unsigned long new_val;
};

struct mmrm_client_notifier_data {
	enum mmrm_cb_type cb_type;
	union {
		struct mmrm_res_val_chng val_chng;
	} cb_data;
	void *pvt_data;
};

struct mmrm_clk_client_desc {
	u32 client_domain;
	u32 client_id;
	const char name[MMRM_CLK_CLIENT_NAME_SIZE];
	struct clk *clk;
	/* CESTA data */
	u32 hw_drv_instances;
	u32 num_pwr_states;
};

struct mmrm_client_desc {
	enum mmrm_client_type client_type;
	union {
		struct mmrm_clk_client_desc desc;
	} client_info;
	enum mmrm_client_priority priority;
	void *pvt_data;
	int (*notifier_callback_fn)(
		void *notifier_data);
};

/* Stub definitions for <soc/qcom/crm.h> */
#ifndef _SOC_QCOM_CRM_H_
#define _SOC_QCOM_CRM_H_

/* Define any necessary structures or functions from crm.h */
static inline int qcom_scm_mem_protect_sd_ctrl(u32 device_id, phys_addr_t mem_addr,
		u64 mem_size, u32 vmid)
{
	/* Stub implementation */
	return 0;
}

#endif /* _SOC_QCOM_CRM_H_ */

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

struct qtee_shm {
	phys_addr_t paddr;
	void *vaddr;
	size_t size;
};

enum vmid {
	VMID_TZ = 0x1,
	VMID_HLOS = 0x3,
	VMID_CP_TOUCH = 0x8,
	VMID_CP_BITSTREAM = 0x9,
	VMID_CP_PIXEL = 0xA,
	VMID_CP_NON_PIXEL = 0xB,
	VMID_CP_CAMERA = 0xD,
	VMID_HLOS_FREE = 0xE,
	VMID_MSS_MSA = 0xF,
	VMID_MSS_NONMSA = 0x10,
	VMID_CP_SEC_DISPLAY = 0x11,
	VMID_CP_APP = 0x12,
	VMID_LPASS = 0x16,
	VMID_WLAN = 0x18,
	VMID_WLAN_CE = 0x19,
	VMID_CP_SPSS_SP = 0x1A,
	VMID_CP_CAMERA_PREVIEW = 0x1D,
	VMID_CP_SPSS_SP_SHARED = 0x22,
	VMID_CP_SPSS_HLOS_SHARED = 0x24,
	VMID_ADSP_HEAP = 0x25,
	VMID_CP_CDSP = 0x2A,
	VMID_NAV = 0x2B,
	VMID_TVM = 0x2D,
	VMID_OEMVM = 0x31,
	VMID_LAST,
	VMID_INVAL = -1
};

/* Stub definitions for <linux/soc/qcom/panel_event_notifier.h> */
#ifndef _LINUX_SOC_QCOM_PANEL_EVENT_NOTIFIER_H_
#define _LINUX_SOC_QCOM_PANEL_EVENT_NOTIFIER_H_

/* Define panel event notifier related structures and functions */
enum panel_event_notifier_tag {
	PANEL_EVENT_NOTIFICATION_NONE,
	PANEL_EVENT_NOTIFICATION_PRIMARY,
	PANEL_EVENT_NOTIFICATION_SECONDARY,
	PANEL_EVENT_NOTIFICATION_MAX
};

enum panel_event_notifier_client {
	PANEL_EVENT_NOTIFIER_CLIENT_PRIMARY_TOUCH,
	PANEL_EVENT_NOTIFIER_CLIENT_SECONDARY_TOUCH,
	PANEL_EVENT_NOTIFIER_CLIENT_ECM,
	PANEL_EVENT_NOTIFIER_CLIENT_MAX
};

enum panel_event_notification_type {
	DRM_PANEL_EVENT_NONE,
	DRM_PANEL_EVENT_BLANK,
	DRM_PANEL_EVENT_UNBLANK,
	DRM_PANEL_EVENT_BLANK_LP,
	DRM_PANEL_EVENT_FPS_CHANGE,
	DRM_PANEL_EVENT_MAX
};

struct panel_event_notification_data {
	int old_fps;
	int new_fps;
	bool early_trigger;
};

struct panel_event_notification {
	enum panel_event_notification_type notif_type;
	void *panel;
	struct panel_event_notification_data notif_data;
};

/*altmode dummy*/
struct altmode_pan_ack_msg {
		u32 cmd_type;
		u8 port_index;
};

enum altmode_send_msg_type {
		ALTMODE_PAN_EN = 0x10,
		ALTMODE_PAN_ACK,
};

/**
 ** struct altmode_client_data
 **	Uniquely define altmode client while registering with altmode framework.
 **
 ** @svid:		Unique ID for Type-C Altmode client devices
 ** @name:		Short descriptive name to identify client
 ** @priv:		Pointer to client driver's internal top level structure
 ** @callback:		Callback function to receive PMIC GLINK message data
 **/
struct altmode_client_data {
		u16	svid;
		const char	*name;
		void		*priv;
		int		(*callback)(void *priv, void *data, size_t len);
};

#if IS_ENABLED(CONFIG_QTI_ALTMODE_GLINK)

struct device;
int altmode_register_notifier(struct device *client_dev, void (*cb)(void *),
					void *priv);
int altmode_deregister_notifier(struct device *client_dev, void *priv);
struct altmode_client *altmode_register_client(struct device *dev,
				const struct altmode_client_data *client_data);
int altmode_deregister_client(struct altmode_client *client);
int altmode_send_data(struct altmode_client *client, void *data, size_t len);

#else

static inline int altmode_register_notifier(struct device *client_dev,
				void (*cb)(void *), void *priv)
{
		return -ENODEV;
}

static inline int altmode_deregister_notifier(struct device *client_dev,
				void *priv)
{
		return -ENODEV;
}

static inline struct altmode_client *altmode_register_client(struct device *dev,
			const struct altmode_client_data *client_data)
{
		return ERR_PTR(-ENODEV);
}

static inline int altmode_deregister_client(struct altmode_client *client)
{
		return -ENODEV;
}

static inline int altmode_send_data(struct altmode_client *client, void *data,
					size_t len)
{
		return -ENODEV;
}

#endif

static inline bool qtee_shmbridge_is_enabled(void)
{
	return false;
}

static inline bool  msm_gpio_get_pin_address(const int gpio_pin, struct resource *res)
{
	return false;
}

static inline void *panel_event_notifier_register(enum panel_event_notifier_tag tag,
		enum panel_event_notifier_client client,
		void *handle,
		void (*cb_fn)(struct panel_event_notification *notification,
				void *data),
		void *data)
{
	/* Stub implementation */
	return NULL;
}

static inline void panel_event_notifier_unregister(void *cookie)
{
	/* Stub implementation */
}

static inline void panel_event_notification_trigger(enum panel_event_notifier_tag tag,
		struct panel_event_notification *notification)
{
	/* Stub implementation */
}

static int llcc_configure_staling_mode(struct llcc_slice_desc *desc,
				struct llcc_staling_mode_params *p)
{
	return -EINVAL;
}

static int llcc_notif_staling_inc_counter(struct llcc_slice_desc *desc)
{
	return -EINVAL;
}

#endif /* _LINUX_SOC_QCOM_PANEL_EVENT_NOTIFIER_H_ */

static inline void *ipc_log_context_destroy(void *ctxt)
{
	return NULL;
}
static inline void ipc_log_string(void *ilctxt, const char *fmt, ...)
{
}
static inline void *ipc_log_context_create(int max_num_pages,
	const char *modname, uint32_t feature_version)
{
	return NULL;
}
/**
 * * of_fdt_get_ddrtype - Return the type of ddr (4/5) on the current device
 * *
 * * On match, returns a non-zero positive value which matches the ddr type.
 * * Otherwise returns -ENOENT.
 **/
static inline int of_fdt_get_ddrtype(void)
{
	int ret;
	u32 ddr_type;
	struct device_node *mem_node;

	mem_node = of_find_node_by_path("/memory");
	if (!mem_node)
		return -ENOENT;

	ret = of_property_read_u32(mem_node, "ddr_device_type", &ddr_type);
	of_node_put(mem_node);
	if (ret < 0)
		return -ENOENT;

	return ddr_type;
}
#endif
