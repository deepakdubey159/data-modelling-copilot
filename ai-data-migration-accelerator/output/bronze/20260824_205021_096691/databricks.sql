CREATE TABLE `audit_log` (
  `audit_id` STRING(255) NOT NULL,
  `operation` STRING(30),
  `operation_timestamp` STRING(255),
  `table_name` STRING(100),
  `user_name` STRING(100),
  CONSTRAINT `pk_audit_log` PRIMARY KEY (`audit_id`)
)
;

CREATE TABLE `category` (
  `category_name` STRING(100) NOT NULL,
  CONSTRAINT `pk_category` PRIMARY KEY (`category_name`)
)
;

CREATE TABLE `city` (
  `city_name` STRING(100) NOT NULL,
  `state_id` STRING(255) NOT NULL,
  CONSTRAINT `pk_city` PRIMARY KEY (`city_name`, `state_id`)
)
;

CREATE TABLE `country` (
  `country_code` STRING(255) NOT NULL,
  `country_name` STRING(100),
  `created_at` STRING(255),
  CONSTRAINT `pk_country` PRIMARY KEY (`country_code`)
)
;

CREATE TABLE `customer` (
  `credit_limit` STRING(255),
  `customer_number` STRING(255) NOT NULL,
  `email` STRING(255),
  `first_name` STRING(100),
  `last_name` STRING(100),
  `phone` STRING(30),
  `status` STRING(30),
  CONSTRAINT `pk_customer` PRIMARY KEY (`customer_number`),
  CONSTRAINT `uq_customer_email` UNIQUE (`email`)
)
;

CREATE TABLE `department` (
  `department_name` STRING(100) NOT NULL,
  CONSTRAINT `pk_department` PRIMARY KEY (`department_name`)
)
;

CREATE TABLE `employee` (
  `email` STRING(255) NOT NULL,
  `first_name` STRING(100),
  `hire_date` STRING(255),
  `last_name` STRING(100),
  `salary` DECIMAL(18,2),
  CONSTRAINT `pk_employee` PRIMARY KEY (`email`)
)
;

CREATE TABLE `inventory` (
  `product_id` STRING(255) NOT NULL,
  `quantity` BIGINT,
  `reorder_level` STRING(255),
  `warehouse_id` STRING(255) NOT NULL,
  CONSTRAINT `pk_inventory` PRIMARY KEY (`warehouse_id`, `product_id`),
  CONSTRAINT `ck_inventory_quantity` CHECK (quantity >= 0)
)
;

CREATE TABLE `order` (
  `order_date` STRING(255),
  `order_id` STRING(255) NOT NULL,
  `order_status` STRING(255),
  CONSTRAINT `pk_order` PRIMARY KEY (`order_id`)
)
;

CREATE TABLE `order_line_item` (
  `line_number` STRING(255) NOT NULL,
  `order_id` STRING(255) NOT NULL,
  `quantity` BIGINT,
  `unit_price` STRING(255),
  CONSTRAINT `pk_order_line_item` PRIMARY KEY (`order_id`, `line_number`),
  CONSTRAINT `ck_order_line_item_quantity` CHECK (quantity >= 0)
)
;

CREATE TABLE `payment` (
  `amount` DECIMAL(18,2),
  `payment_date` STRING(255),
  `payment_id` STRING(255) NOT NULL,
  `payment_method` STRING(255),
  CONSTRAINT `pk_payment` PRIMARY KEY (`payment_id`)
)
;

CREATE TABLE `product` (
  `product_name` STRING(100),
  `sku` STRING(30) NOT NULL,
  `status` STRING(30),
  `unit_price` STRING(255),
  CONSTRAINT `pk_product` PRIMARY KEY (`sku`)
)
;

CREATE TABLE `promotion` (
  `discount_percent` STRING(255),
  `promotion_name` STRING(100) NOT NULL,
  CONSTRAINT `pk_promotion` PRIMARY KEY (`promotion_name`)
)
;

CREATE TABLE `return_order` (
  `return_id` STRING(255) NOT NULL,
  `return_reason` STRING(500),
  CONSTRAINT `pk_return_order` PRIMARY KEY (`return_id`)
)
;

CREATE TABLE `shipment` (
  `shipment_id` STRING(255) NOT NULL,
  `shipped_date` STRING(255),
  `tracking_number` STRING(255),
  CONSTRAINT `pk_shipment` PRIMARY KEY (`shipment_id`),
  CONSTRAINT `uq_shipment_tracking_number` UNIQUE (`tracking_number`)
)
;

CREATE TABLE `state` (
  `country_id` STRING(255) NOT NULL,
  `state_name` STRING(100) NOT NULL,
  CONSTRAINT `pk_state` PRIMARY KEY (`state_name`, `country_id`)
)
;

CREATE TABLE `supplier` (
  `contact_name` STRING(100),
  `email` STRING(255),
  `phone` STRING(30),
  `supplier_name` STRING(100) NOT NULL,
  CONSTRAINT `pk_supplier` PRIMARY KEY (`supplier_name`),
  CONSTRAINT `uq_supplier_email` UNIQUE (`email`)
)
;

CREATE TABLE `warehouse` (
  `warehouse_name` STRING(100) NOT NULL,
  CONSTRAINT `pk_warehouse` PRIMARY KEY (`warehouse_name`)
)
;

CREATE UNIQUE INDEX `idx_audit_log_pk` ON `audit_log`(`audit_id`);

CREATE UNIQUE INDEX `idx_category_pk` ON `category`(`category_name`);

CREATE UNIQUE INDEX `idx_city_pk` ON `city`(`city_name`, `state_id`);

CREATE UNIQUE INDEX `idx_country_pk` ON `country`(`country_code`);

CREATE UNIQUE INDEX `idx_customer_email` ON `customer`(`email`);

CREATE UNIQUE INDEX `idx_customer_pk` ON `customer`(`customer_number`);

CREATE UNIQUE INDEX `idx_department_pk` ON `department`(`department_name`);

CREATE UNIQUE INDEX `idx_employee_pk` ON `employee`(`email`);

CREATE UNIQUE INDEX `idx_inventory_pk` ON `inventory`(`warehouse_id`, `product_id`);

CREATE UNIQUE INDEX `idx_order_pk` ON `order`(`order_id`);

CREATE UNIQUE INDEX `idx_order_line_item_pk` ON `order_line_item`(`order_id`, `line_number`);

CREATE UNIQUE INDEX `idx_payment_pk` ON `payment`(`payment_id`);

CREATE UNIQUE INDEX `idx_product_pk` ON `product`(`sku`);

CREATE UNIQUE INDEX `idx_promotion_pk` ON `promotion`(`promotion_name`);

CREATE UNIQUE INDEX `idx_return_order_pk` ON `return_order`(`return_id`);

CREATE UNIQUE INDEX `idx_shipment_pk` ON `shipment`(`shipment_id`);

CREATE UNIQUE INDEX `idx_shipment_tracking_number` ON `shipment`(`tracking_number`);

CREATE UNIQUE INDEX `idx_state_pk` ON `state`(`state_name`, `country_id`);

CREATE UNIQUE INDEX `idx_supplier_email` ON `supplier`(`email`);

CREATE UNIQUE INDEX `idx_supplier_pk` ON `supplier`(`supplier_name`);

CREATE UNIQUE INDEX `idx_warehouse_pk` ON `warehouse`(`warehouse_name`);

ALTER TABLE `audit_log` CHANGE COLUMN `audit_id` COMMENT 'Source: audit_id | Physical type: STRING';

ALTER TABLE `audit_log` CHANGE COLUMN `operation` COMMENT 'Source: operation | Physical type: STRING';

ALTER TABLE `audit_log` CHANGE COLUMN `operation_timestamp` COMMENT 'Source: operation_timestamp | Physical type: STRING';

ALTER TABLE `audit_log` CHANGE COLUMN `table_name` COMMENT 'Source: table_name | Physical type: STRING';

ALTER TABLE `audit_log` CHANGE COLUMN `user_name` COMMENT 'Source: user_name | Physical type: STRING';

ALTER TABLE `category` CHANGE COLUMN `category_name` COMMENT 'Source: category_name | Physical type: STRING';

ALTER TABLE `city` CHANGE COLUMN `city_name` COMMENT 'Source: city_name | Physical type: STRING';

ALTER TABLE `city` CHANGE COLUMN `state_id` COMMENT 'Source: state_id | Physical type: STRING';

ALTER TABLE `country` CHANGE COLUMN `country_code` COMMENT 'Source: country_code | Physical type: STRING';

ALTER TABLE `country` CHANGE COLUMN `country_name` COMMENT 'Source: country_name | Physical type: STRING';

ALTER TABLE `country` CHANGE COLUMN `created_at` COMMENT 'Source: created_at | Physical type: STRING';

ALTER TABLE `customer` CHANGE COLUMN `credit_limit` COMMENT 'Source: credit_limit | Physical type: STRING';

ALTER TABLE `customer` CHANGE COLUMN `customer_number` COMMENT 'Source: customer_number | Physical type: STRING';

ALTER TABLE `customer` CHANGE COLUMN `email` COMMENT 'Source: email | Physical type: STRING';

ALTER TABLE `customer` CHANGE COLUMN `first_name` COMMENT 'Source: first_name | Physical type: STRING';

ALTER TABLE `customer` CHANGE COLUMN `last_name` COMMENT 'Source: last_name | Physical type: STRING';

ALTER TABLE `customer` CHANGE COLUMN `phone` COMMENT 'Source: phone | Physical type: STRING';

ALTER TABLE `customer` CHANGE COLUMN `status` COMMENT 'Source: status | Physical type: STRING';

ALTER TABLE `department` CHANGE COLUMN `department_name` COMMENT 'Source: department_name | Physical type: STRING';

ALTER TABLE `employee` CHANGE COLUMN `email` COMMENT 'Source: email | Physical type: STRING';

ALTER TABLE `employee` CHANGE COLUMN `first_name` COMMENT 'Source: first_name | Physical type: STRING';

ALTER TABLE `employee` CHANGE COLUMN `hire_date` COMMENT 'Source: hire_date | Physical type: STRING';

ALTER TABLE `employee` CHANGE COLUMN `last_name` COMMENT 'Source: last_name | Physical type: STRING';

ALTER TABLE `employee` CHANGE COLUMN `salary` COMMENT 'Source: salary | Physical type: DECIMAL';

ALTER TABLE `inventory` CHANGE COLUMN `product_id` COMMENT 'Source: product_id | Physical type: STRING';

ALTER TABLE `inventory` CHANGE COLUMN `quantity` COMMENT 'Source: quantity | Physical type: INTEGER';

ALTER TABLE `inventory` CHANGE COLUMN `reorder_level` COMMENT 'Source: reorder_level | Physical type: STRING';

ALTER TABLE `inventory` CHANGE COLUMN `warehouse_id` COMMENT 'Source: warehouse_id | Physical type: STRING';

ALTER TABLE `order` CHANGE COLUMN `order_date` COMMENT 'Source: order_date | Physical type: STRING';

ALTER TABLE `order` CHANGE COLUMN `order_id` COMMENT 'Source: order_id | Physical type: STRING';

ALTER TABLE `order` CHANGE COLUMN `order_status` COMMENT 'Source: order_status | Physical type: STRING';

ALTER TABLE `order_line_item` CHANGE COLUMN `line_number` COMMENT 'Source: line_number | Physical type: STRING';

ALTER TABLE `order_line_item` CHANGE COLUMN `order_id` COMMENT 'Source: order_id | Physical type: STRING';

ALTER TABLE `order_line_item` CHANGE COLUMN `quantity` COMMENT 'Source: quantity | Physical type: INTEGER';

ALTER TABLE `order_line_item` CHANGE COLUMN `unit_price` COMMENT 'Source: unit_price | Physical type: STRING';

ALTER TABLE `payment` CHANGE COLUMN `amount` COMMENT 'Source: amount | Physical type: DECIMAL';

ALTER TABLE `payment` CHANGE COLUMN `payment_date` COMMENT 'Source: payment_date | Physical type: STRING';

ALTER TABLE `payment` CHANGE COLUMN `payment_id` COMMENT 'Source: payment_id | Physical type: STRING';

ALTER TABLE `payment` CHANGE COLUMN `payment_method` COMMENT 'Source: payment_method | Physical type: STRING';

ALTER TABLE `product` CHANGE COLUMN `product_name` COMMENT 'Source: product_name | Physical type: STRING';

ALTER TABLE `product` CHANGE COLUMN `sku` COMMENT 'Source: sku | Physical type: STRING';

ALTER TABLE `product` CHANGE COLUMN `status` COMMENT 'Source: status | Physical type: STRING';

ALTER TABLE `product` CHANGE COLUMN `unit_price` COMMENT 'Source: unit_price | Physical type: STRING';

ALTER TABLE `promotion` CHANGE COLUMN `discount_percent` COMMENT 'Source: discount_percent | Physical type: STRING';

ALTER TABLE `promotion` CHANGE COLUMN `promotion_name` COMMENT 'Source: promotion_name | Physical type: STRING';

ALTER TABLE `return_order` CHANGE COLUMN `return_id` COMMENT 'Source: return_id | Physical type: STRING';

ALTER TABLE `return_order` CHANGE COLUMN `return_reason` COMMENT 'Source: return_reason | Physical type: STRING';

ALTER TABLE `shipment` CHANGE COLUMN `shipment_id` COMMENT 'Source: shipment_id | Physical type: STRING';

ALTER TABLE `shipment` CHANGE COLUMN `shipped_date` COMMENT 'Source: shipped_date | Physical type: STRING';

ALTER TABLE `shipment` CHANGE COLUMN `tracking_number` COMMENT 'Source: tracking_number | Physical type: STRING';

ALTER TABLE `state` CHANGE COLUMN `country_id` COMMENT 'Source: country_id | Physical type: STRING';

ALTER TABLE `state` CHANGE COLUMN `state_name` COMMENT 'Source: state_name | Physical type: STRING';

ALTER TABLE `supplier` CHANGE COLUMN `contact_name` COMMENT 'Source: contact_name | Physical type: STRING';

ALTER TABLE `supplier` CHANGE COLUMN `email` COMMENT 'Source: email | Physical type: STRING';

ALTER TABLE `supplier` CHANGE COLUMN `phone` COMMENT 'Source: phone | Physical type: STRING';

ALTER TABLE `supplier` CHANGE COLUMN `supplier_name` COMMENT 'Source: supplier_name | Physical type: STRING';

ALTER TABLE `warehouse` CHANGE COLUMN `warehouse_name` COMMENT 'Source: warehouse_name | Physical type: STRING';
