/* SPDX-License-Identifier: GPL-2.0-only */
/*
 * Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
 */

#ifndef _MSM_OF_GPIO_COMPAT_H_
#define _MSM_OF_GPIO_COMPAT_H_

#include <linux/version.h>

#if (KERNEL_VERSION(7, 1, 0) > LINUX_VERSION_CODE)
#include <linux/of_gpio.h>
#else
#include <linux/of.h>
#include <linux/gpio/consumer.h>

/**
 * of_get_named_gpio - get a GPIO number from a DT property (legacy integer API)
 * @np:       device node
 * @propname: name of the GPIO property
 * @index:    index of the GPIO within the property
 *
 * Returns a Linux GPIO number on success, or a negative errno on failure.
 * This shim preserves the legacy integer-GPIO calling convention for
 * out-of-tree drivers that have not yet migrated to the descriptor API.
 *
 * fwnode_gpiod_get_index() does not mutate the fwnode; the non-const
 * signature is a kernel API oversight.
 * The cast to (struct fwnode_handle *) drops the const qualifier that
 * of_fwnode_handle() preserves from its const device_node argument.
 * fwnode_gpiod_get_index() does not mutate the fwnode; the non-const
 * signature is a kernel API oversight.
 */
static inline int of_get_named_gpio(const struct device_node *np,
				    const char *propname, int index)
{
	struct gpio_desc *desc;

	desc = fwnode_gpiod_get_index(
			(struct fwnode_handle *)of_fwnode_handle(np),
			propname, index, GPIOD_ASIS, __func__);
	if (IS_ERR(desc))
		return PTR_ERR(desc);

	return desc_to_gpio(desc);
}
#endif /* KERNEL_VERSION(7, 1, 0) > LINUX_VERSION_CODE */

#endif /* _MSM_OF_GPIO_COMPAT_H_ */
