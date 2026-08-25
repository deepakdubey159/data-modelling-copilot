CREATE TABLE `audit_log` (
  `operation` STRING(30),
  `operation_timestamp` STRING(255) NOT NULL,
  `table_name` STRING(100) NOT NULL,
  `user_name` STRING(100) NOT NULL,
  CONSTRAINT `pk_audit_log` PRIMARY KEY (`operation_timestamp`, `table_name`, `user_name`)
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
  `state_name` STRING(100) NOT NULL,
  CONSTRAINT `pk_city` PRIMARY KEY (`city_name`, `state_id`)
)
CLUSTERED BY (`city_name`, `state_id`)
;

CREATE TABLE `country` (
  `country_code` STRING(255) NOT NULL,
  `country_name` STRING(100),
  `created_at` STRING(255),
  CONSTRAINT `pk_country` PRIMARY KEY (`country_code`)
)
;

CREATE TABLE `customer` (
  `city_name` STRING(100),
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
CLUSTERED BY (`customer_number`)
;

CREATE TABLE `department` (
  `department_name` STRING(100) NOT NULL,
  CONSTRAINT `pk_department` PRIMARY KEY (`department_name`)
)
;

CREATE TABLE `employee` (
  `department_name` STRING(100),
  `email` STRING(255) NOT NULL,
  `first_name` STRING(100),
  `hire_date` STRING(255),
  `last_name` STRING(100),
  `parent_email` STRING(255),
  `salary` DECIMAL(18,2),
  CONSTRAINT `pk_employee` PRIMARY KEY (`email`)
)
CLUSTERED BY (`email`)
;

CREATE TABLE `inventory` (
  `product_id` STRING(255) NOT NULL,
  `product_sku` STRING(30) NOT NULL,
  `quantity` BIGINT,
  `reorder_level` STRING(255),
  `warehouse_id` STRING(255) NOT NULL,
  `warehouse_name` STRING(100) NOT NULL,
  CONSTRAINT `pk_inventory` PRIMARY KEY (`warehouse_id`, `product_id`),
  CONSTRAINT `ck_inventory_quantity` CHECK (quantity >= 0)
)
CLUSTERED BY (`product_sku`, `warehouse_name`)
;

CREATE TABLE `order` (
  `customer_number` STRING(255),
  `employee_email` STRING(255),
  `order_date` STRING(255),
  `order_id` STRING(255) NOT NULL,
  `order_status` STRING(255),
  CONSTRAINT `pk_order` PRIMARY KEY (`order_id`)
)
CLUSTERED BY (`order_id`)
;

CREATE TABLE `order_item` (
  `line_number` STRING(255) NOT NULL,
  `order_id` STRING(255) NOT NULL,
  `product_sku` STRING(30),
  `quantity` BIGINT,
  `unit_price` STRING(255),
  CONSTRAINT `pk_order_item` PRIMARY KEY (`order_id`, `line_number`),
  CONSTRAINT `ck_order_item_quantity` CHECK (quantity >= 0)
)
CLUSTERED BY (`order_id`, `product_sku`)
;

CREATE TABLE `payment` (
  `amount` DECIMAL(18,2),
  `order_id` STRING(255),
  `payment_date` STRING(255),
  `payment_id` STRING(255) NOT NULL,
  `payment_method` STRING(255),
  CONSTRAINT `pk_payment` PRIMARY KEY (`payment_id`)
)
CLUSTERED BY (`order_id`)
;

CREATE TABLE `product` (
  `category_name` STRING(100),
  `product_name` STRING(100),
  `sku` STRING(30) NOT NULL,
  `status` STRING(30),
  `supplier_name` STRING(100),
  `unit_price` STRING(255),
  CONSTRAINT `pk_product` PRIMARY KEY (`sku`)
)
CLUSTERED BY (`sku`)
;

CREATE TABLE `product_promotion_association` (
  `product_sku` STRING(30) NOT NULL,
  `promotion_name` STRING(100) NOT NULL,
  CONSTRAINT `pk_product_promotion` PRIMARY KEY (`product_sku`, `promotion_name`)
)
CLUSTERED BY (`product_sku`, `promotion_name`)
;

CREATE TABLE `product_warehouse_association` (
  `product_sku` STRING(30) NOT NULL,
  `warehouse_name` STRING(100) NOT NULL,
  CONSTRAINT `pk_product_warehouse` PRIMARY KEY (`product_sku`, `warehouse_name`)
)
CLUSTERED BY (`product_sku`, `warehouse_name`)
;

CREATE TABLE `promotion` (
  `discount_percent` STRING(255),
  `promotion_name` STRING(100) NOT NULL,
  CONSTRAINT `pk_promotion` PRIMARY KEY (`promotion_name`)
)
;

CREATE TABLE `return` (
  `order_id` STRING(255),
  `product_sku` STRING(30),
  `return_id` STRING(255) NOT NULL,
  `return_reason` STRING(500),
  CONSTRAINT `pk_return` PRIMARY KEY (`return_id`)
)
CLUSTERED BY (`order_id`, `product_sku`)
;

CREATE TABLE `shipment` (
  `order_id` STRING(255),
  `shipped_date` STRING(255),
  `tracking_number` STRING(255) NOT NULL,
  `warehouse_name` STRING(100),
  CONSTRAINT `pk_shipment` PRIMARY KEY (`tracking_number`)
)
CLUSTERED BY (`order_id`, `warehouse_name`)
;

CREATE TABLE `state` (
  `country_code` STRING(255) NOT NULL,
  `country_id` STRING(255) NOT NULL,
  `state_name` STRING(100) NOT NULL,
  CONSTRAINT `pk_state` PRIMARY KEY (`state_name`, `country_id`)
)
CLUSTERED BY (`state_name`, `country_id`)
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
  `city_name` STRING(100),
  `warehouse_name` STRING(100) NOT NULL,
  CONSTRAINT `pk_warehouse` PRIMARY KEY (`warehouse_name`)
)
CLUSTERED BY (`warehouse_name`)
;

ALTER TABLE `city` ADD CONSTRAINT `fk_city_state_name` FOREIGN KEY (`state_name`) REFERENCES `state`(`state_name`);

ALTER TABLE `customer` ADD CONSTRAINT `fk_customer_city_name` FOREIGN KEY (`city_name`) REFERENCES `city`(`city_name`);

ALTER TABLE `employee` ADD CONSTRAINT `fk_employee_department_name` FOREIGN KEY (`department_name`) REFERENCES `department`(`department_name`);

ALTER TABLE `employee` ADD CONSTRAINT `fk_employee_parent_email` FOREIGN KEY (`parent_email`) REFERENCES `employee`(`email`);

ALTER TABLE `inventory` ADD CONSTRAINT `fk_inventory_product_sku` FOREIGN KEY (`product_sku`) REFERENCES `product`(`sku`);

ALTER TABLE `inventory` ADD CONSTRAINT `fk_inventory_warehouse_name` FOREIGN KEY (`warehouse_name`) REFERENCES `warehouse`(`warehouse_name`);

ALTER TABLE `order` ADD CONSTRAINT `fk_order_customer_number` FOREIGN KEY (`customer_number`) REFERENCES `customer`(`customer_number`);

ALTER TABLE `order` ADD CONSTRAINT `fk_order_employee_email` FOREIGN KEY (`employee_email`) REFERENCES `employee`(`email`);

ALTER TABLE `order_item` ADD CONSTRAINT `fk_order_item_order_id` FOREIGN KEY (`order_id`) REFERENCES `order`(`order_id`);

ALTER TABLE `order_item` ADD CONSTRAINT `fk_order_item_product_sku` FOREIGN KEY (`product_sku`) REFERENCES `product`(`sku`);

ALTER TABLE `payment` ADD CONSTRAINT `fk_payment_order_id` FOREIGN KEY (`order_id`) REFERENCES `order`(`order_id`);

ALTER TABLE `product` ADD CONSTRAINT `fk_product_category_name` FOREIGN KEY (`category_name`) REFERENCES `category`(`category_name`);

ALTER TABLE `product` ADD CONSTRAINT `fk_product_supplier_name` FOREIGN KEY (`supplier_name`) REFERENCES `supplier`(`supplier_name`);

ALTER TABLE `product_promotion_association` ADD CONSTRAINT `fk_product_promotion` FOREIGN KEY (`product_sku`) REFERENCES `product`(`sku`);

ALTER TABLE `product_promotion_association` ADD CONSTRAINT `fk_product_promotion` FOREIGN KEY (`promotion_name`) REFERENCES `promotion`(`promotion_name`);

ALTER TABLE `product_warehouse_association` ADD CONSTRAINT `fk_product_warehouse` FOREIGN KEY (`product_sku`) REFERENCES `product`(`sku`);

ALTER TABLE `product_warehouse_association` ADD CONSTRAINT `fk_product_warehouse` FOREIGN KEY (`warehouse_name`) REFERENCES `warehouse`(`warehouse_name`);

ALTER TABLE `return` ADD CONSTRAINT `fk_return_order_id` FOREIGN KEY (`order_id`) REFERENCES `order`(`order_id`);

ALTER TABLE `return` ADD CONSTRAINT `fk_return_product_sku` FOREIGN KEY (`product_sku`) REFERENCES `product`(`sku`);

ALTER TABLE `shipment` ADD CONSTRAINT `fk_shipment_order_id` FOREIGN KEY (`order_id`) REFERENCES `order`(`order_id`);

ALTER TABLE `shipment` ADD CONSTRAINT `fk_shipment_warehouse_name` FOREIGN KEY (`warehouse_name`) REFERENCES `warehouse`(`warehouse_name`);

ALTER TABLE `state` ADD CONSTRAINT `fk_state_country_code` FOREIGN KEY (`country_code`) REFERENCES `country`(`country_code`);

ALTER TABLE `warehouse` ADD CONSTRAINT `fk_warehouse_city_name` FOREIGN KEY (`city_name`) REFERENCES `city`(`city_name`);

CREATE UNIQUE INDEX `idx_audit_log_pk` ON `audit_log`(`operation_timestamp`, `table_name`, `user_name`);

CREATE UNIQUE INDEX `idx_category_pk` ON `category`(`category_name`);

CREATE UNIQUE INDEX `idx_city_pk` ON `city`(`city_name`, `state_id`);

CREATE INDEX `idx_city_state_name` ON `city`(`state_name`);

CREATE UNIQUE INDEX `idx_country_pk` ON `country`(`country_code`);

CREATE INDEX `idx_customer_city_name` ON `customer`(`city_name`);

CREATE UNIQUE INDEX `idx_customer_email` ON `customer`(`email`);

CREATE UNIQUE INDEX `idx_customer_pk` ON `customer`(`customer_number`);

CREATE UNIQUE INDEX `idx_department_pk` ON `department`(`department_name`);

CREATE INDEX `idx_employee_department_name` ON `employee`(`department_name`);

CREATE INDEX `idx_employee_parent_email` ON `employee`(`parent_email`);

CREATE UNIQUE INDEX `idx_employee_pk` ON `employee`(`email`);

CREATE UNIQUE INDEX `idx_inventory_pk` ON `inventory`(`warehouse_id`, `product_id`);

CREATE INDEX `idx_inventory_product_sku` ON `inventory`(`product_sku`);

CREATE INDEX `idx_inventory_warehouse_name` ON `inventory`(`warehouse_name`);

CREATE INDEX `idx_order_customer_number` ON `order`(`customer_number`);

CREATE INDEX `idx_order_employee_email` ON `order`(`employee_email`);

CREATE UNIQUE INDEX `idx_order_pk` ON `order`(`order_id`);

CREATE UNIQUE INDEX `idx_order_item_pk` ON `order_item`(`order_id`, `line_number`);

CREATE INDEX `idx_order_item_product_sku` ON `order_item`(`product_sku`);

CREATE INDEX `idx_payment_order_id` ON `payment`(`order_id`);

CREATE UNIQUE INDEX `idx_payment_pk` ON `payment`(`payment_id`);

CREATE INDEX `idx_product_category_name` ON `product`(`category_name`);

CREATE UNIQUE INDEX `idx_product_pk` ON `product`(`sku`);

CREATE INDEX `idx_product_supplier_name` ON `product`(`supplier_name`);

CREATE UNIQUE INDEX `idx_product_promotion` ON `product_promotion_association`(`product_sku`, `promotion_name`);

CREATE INDEX `idx_product_promotion` ON `product_promotion_association`(`promotion_name`);

CREATE UNIQUE INDEX `idx_product_warehouse` ON `product_warehouse_association`(`product_sku`, `warehouse_name`);

CREATE INDEX `idx_product_warehouse` ON `product_warehouse_association`(`warehouse_name`);

CREATE UNIQUE INDEX `idx_promotion_pk` ON `promotion`(`promotion_name`);

CREATE INDEX `idx_return_order_id` ON `return`(`order_id`);

CREATE UNIQUE INDEX `idx_return_pk` ON `return`(`return_id`);

CREATE INDEX `idx_return_product_sku` ON `return`(`product_sku`);

CREATE INDEX `idx_shipment_order_id` ON `shipment`(`order_id`);

CREATE UNIQUE INDEX `idx_shipment_pk` ON `shipment`(`tracking_number`);

CREATE INDEX `idx_shipment_warehouse_name` ON `shipment`(`warehouse_name`);

CREATE INDEX `idx_state_country_code` ON `state`(`country_code`);

CREATE UNIQUE INDEX `idx_state_pk` ON `state`(`state_name`, `country_id`);

CREATE UNIQUE INDEX `idx_supplier_email` ON `supplier`(`email`);

CREATE UNIQUE INDEX `idx_supplier_pk` ON `supplier`(`supplier_name`);

CREATE INDEX `idx_warehouse_city_name` ON `warehouse`(`city_name`);

CREATE UNIQUE INDEX `idx_warehouse_pk` ON `warehouse`(`warehouse_name`);

-- Partition/Clustering Recommendation: CLUSTER BY: city_name, state_id | Rationale: Master data is looked up by key; clustering on it keeps those reads to a minimum of blocks.

-- Partition/Clustering Recommendation: CLUSTER BY: customer_number | Rationale: Master data is looked up by key; clustering on it keeps those reads to a minimum of blocks.

-- Partition/Clustering Recommendation: CLUSTER BY: email | Rationale: Master data is looked up by key; clustering on it keeps those reads to a minimum of blocks.

-- Partition/Clustering Recommendation: CLUSTER BY: product_sku, warehouse_name | Rationale: Clustering on product_sku, warehouse_name co-locates rows that are joined and filtered together.

-- Partition/Clustering Recommendation: CLUSTER BY: order_id | Rationale: Master data is looked up by key; clustering on it keeps those reads to a minimum of blocks.

-- Partition/Clustering Recommendation: CLUSTER BY: order_id, product_sku | Rationale: Clustering on order_id, product_sku co-locates rows that are joined and filtered together.

-- Partition/Clustering Recommendation: CLUSTER BY: order_id | Rationale: Clustering on order_id co-locates rows that are joined and filtered together.

-- Partition/Clustering Recommendation: CLUSTER BY: sku | Rationale: Master data is looked up by key; clustering on it keeps those reads to a minimum of blocks.

-- Partition/Clustering Recommendation: CLUSTER BY: product_sku, promotion_name | Rationale: Clustering on product_sku, promotion_name co-locates rows that are joined and filtered together.

-- Partition/Clustering Recommendation: CLUSTER BY: product_sku, warehouse_name | Rationale: Clustering on product_sku, warehouse_name co-locates rows that are joined and filtered together.

-- Partition/Clustering Recommendation: CLUSTER BY: order_id, product_sku | Rationale: Clustering on order_id, product_sku co-locates rows that are joined and filtered together.

-- Partition/Clustering Recommendation: CLUSTER BY: order_id, warehouse_name | Rationale: Clustering on order_id, warehouse_name co-locates rows that are joined and filtered together.

-- Partition/Clustering Recommendation: CLUSTER BY: state_name, country_id | Rationale: Master data is looked up by key; clustering on it keeps those reads to a minimum of blocks.

-- Partition/Clustering Recommendation: CLUSTER BY: warehouse_name | Rationale: Master data is looked up by key; clustering on it keeps those reads to a minimum of blocks.

ALTER TABLE `audit_log` CHANGE COLUMN `operation` COMMENT 'Source: operation | Physical type: STRING';

ALTER TABLE `audit_log` CHANGE COLUMN `operation_timestamp` COMMENT 'Source: operation_timestamp | Physical type: STRING';

ALTER TABLE `audit_log` CHANGE COLUMN `table_name` COMMENT 'Source: table_name | Physical type: STRING';

ALTER TABLE `audit_log` CHANGE COLUMN `user_name` COMMENT 'Source: user_name | Physical type: STRING';

ALTER TABLE `category` CHANGE COLUMN `category_name` COMMENT 'Source: category_name | Physical type: STRING';

ALTER TABLE `city` CHANGE COLUMN `city_name` COMMENT 'Source: city_name | Physical type: STRING';

ALTER TABLE `city` CHANGE COLUMN `state_id` COMMENT 'Source: state_id | Physical type: STRING';

ALTER TABLE `city` CHANGE COLUMN `state_name` COMMENT 'Source: state_name | Physical type: STRING';

ALTER TABLE `country` CHANGE COLUMN `country_code` COMMENT 'Source: country_code | Physical type: STRING';

ALTER TABLE `country` CHANGE COLUMN `country_name` COMMENT 'Source: country_name | Physical type: STRING';

ALTER TABLE `country` CHANGE COLUMN `created_at` COMMENT 'Source: created_at | Physical type: STRING';

ALTER TABLE `customer` CHANGE COLUMN `city_name` COMMENT 'Source: city_name | Physical type: STRING';

ALTER TABLE `customer` CHANGE COLUMN `credit_limit` COMMENT 'Source: credit_limit | Physical type: STRING';

ALTER TABLE `customer` CHANGE COLUMN `customer_number` COMMENT 'Source: customer_number | Physical type: STRING';

ALTER TABLE `customer` CHANGE COLUMN `email` COMMENT 'Source: email | Physical type: STRING';

ALTER TABLE `customer` CHANGE COLUMN `first_name` COMMENT 'Source: first_name | Physical type: STRING';

ALTER TABLE `customer` CHANGE COLUMN `last_name` COMMENT 'Source: last_name | Physical type: STRING';

ALTER TABLE `customer` CHANGE COLUMN `phone` COMMENT 'Source: phone | Physical type: STRING';

ALTER TABLE `customer` CHANGE COLUMN `status` COMMENT 'Source: status | Physical type: STRING';

ALTER TABLE `department` CHANGE COLUMN `department_name` COMMENT 'Source: department_name | Physical type: STRING';

ALTER TABLE `employee` CHANGE COLUMN `department_name` COMMENT 'Source: department_name | Physical type: STRING';

ALTER TABLE `employee` CHANGE COLUMN `email` COMMENT 'Source: email | Physical type: STRING';

ALTER TABLE `employee` CHANGE COLUMN `first_name` COMMENT 'Source: first_name | Physical type: STRING';

ALTER TABLE `employee` CHANGE COLUMN `hire_date` COMMENT 'Source: hire_date | Physical type: STRING';

ALTER TABLE `employee` CHANGE COLUMN `last_name` COMMENT 'Source: last_name | Physical type: STRING';

ALTER TABLE `employee` CHANGE COLUMN `parent_email` COMMENT 'Source: parent_email | Physical type: STRING';

ALTER TABLE `employee` CHANGE COLUMN `salary` COMMENT 'Source: salary | Physical type: DECIMAL';

ALTER TABLE `inventory` CHANGE COLUMN `product_id` COMMENT 'Source: product_id | Physical type: STRING';

ALTER TABLE `inventory` CHANGE COLUMN `product_sku` COMMENT 'Source: product_sku | Physical type: STRING';

ALTER TABLE `inventory` CHANGE COLUMN `quantity` COMMENT 'Source: quantity | Physical type: INTEGER';

ALTER TABLE `inventory` CHANGE COLUMN `reorder_level` COMMENT 'Source: reorder_level | Physical type: STRING';

ALTER TABLE `inventory` CHANGE COLUMN `warehouse_id` COMMENT 'Source: warehouse_id | Physical type: STRING';

ALTER TABLE `inventory` CHANGE COLUMN `warehouse_name` COMMENT 'Source: warehouse_name | Physical type: STRING';

ALTER TABLE `order` CHANGE COLUMN `customer_number` COMMENT 'Source: customer_number | Physical type: STRING';

ALTER TABLE `order` CHANGE COLUMN `employee_email` COMMENT 'Source: employee_email | Physical type: STRING';

ALTER TABLE `order` CHANGE COLUMN `order_date` COMMENT 'Source: order_date | Physical type: STRING';

ALTER TABLE `order` CHANGE COLUMN `order_id` COMMENT 'Source: order_id | Physical type: STRING';

ALTER TABLE `order` CHANGE COLUMN `order_status` COMMENT 'Source: order_status | Physical type: STRING';

ALTER TABLE `order_item` CHANGE COLUMN `line_number` COMMENT 'Source: line_number | Physical type: STRING';

ALTER TABLE `order_item` CHANGE COLUMN `order_id` COMMENT 'Source: order_id | Physical type: STRING';

ALTER TABLE `order_item` CHANGE COLUMN `product_sku` COMMENT 'Source: product_sku | Physical type: STRING';

ALTER TABLE `order_item` CHANGE COLUMN `quantity` COMMENT 'Source: quantity | Physical type: INTEGER';

ALTER TABLE `order_item` CHANGE COLUMN `unit_price` COMMENT 'Source: unit_price | Physical type: STRING';

ALTER TABLE `payment` CHANGE COLUMN `amount` COMMENT 'Source: amount | Physical type: DECIMAL';

ALTER TABLE `payment` CHANGE COLUMN `order_id` COMMENT 'Source: order_id | Physical type: STRING';

ALTER TABLE `payment` CHANGE COLUMN `payment_date` COMMENT 'Source: payment_date | Physical type: STRING';

ALTER TABLE `payment` CHANGE COLUMN `payment_id` COMMENT 'Source: payment_id | Physical type: STRING';

ALTER TABLE `payment` CHANGE COLUMN `payment_method` COMMENT 'Source: payment_method | Physical type: STRING';

ALTER TABLE `product` CHANGE COLUMN `category_name` COMMENT 'Source: category_name | Physical type: STRING';

ALTER TABLE `product` CHANGE COLUMN `product_name` COMMENT 'Source: product_name | Physical type: STRING';

ALTER TABLE `product` CHANGE COLUMN `sku` COMMENT 'Source: sku | Physical type: STRING';

ALTER TABLE `product` CHANGE COLUMN `status` COMMENT 'Source: status | Physical type: STRING';

ALTER TABLE `product` CHANGE COLUMN `supplier_name` COMMENT 'Source: supplier_name | Physical type: STRING';

ALTER TABLE `product` CHANGE COLUMN `unit_price` COMMENT 'Source: unit_price | Physical type: STRING';

ALTER TABLE `product_promotion_association` CHANGE COLUMN `product_sku` COMMENT 'Source: product_sku | Physical type: STRING';

ALTER TABLE `product_promotion_association` CHANGE COLUMN `promotion_name` COMMENT 'Source: promotion_name | Physical type: STRING';

ALTER TABLE `product_warehouse_association` CHANGE COLUMN `product_sku` COMMENT 'Source: product_sku | Physical type: STRING';

ALTER TABLE `product_warehouse_association` CHANGE COLUMN `warehouse_name` COMMENT 'Source: warehouse_name | Physical type: STRING';

ALTER TABLE `promotion` CHANGE COLUMN `discount_percent` COMMENT 'Source: discount_percent | Physical type: STRING';

ALTER TABLE `promotion` CHANGE COLUMN `promotion_name` COMMENT 'Source: promotion_name | Physical type: STRING';

ALTER TABLE `return` CHANGE COLUMN `order_id` COMMENT 'Source: order_id | Physical type: STRING';

ALTER TABLE `return` CHANGE COLUMN `product_sku` COMMENT 'Source: product_sku | Physical type: STRING';

ALTER TABLE `return` CHANGE COLUMN `return_id` COMMENT 'Source: return_id | Physical type: STRING';

ALTER TABLE `return` CHANGE COLUMN `return_reason` COMMENT 'Source: return_reason | Physical type: STRING';

ALTER TABLE `shipment` CHANGE COLUMN `order_id` COMMENT 'Source: order_id | Physical type: STRING';

ALTER TABLE `shipment` CHANGE COLUMN `shipped_date` COMMENT 'Source: shipped_date | Physical type: STRING';

ALTER TABLE `shipment` CHANGE COLUMN `tracking_number` COMMENT 'Source: tracking_number | Physical type: STRING';

ALTER TABLE `shipment` CHANGE COLUMN `warehouse_name` COMMENT 'Source: warehouse_name | Physical type: STRING';

ALTER TABLE `state` CHANGE COLUMN `country_code` COMMENT 'Source: country_code | Physical type: STRING';

ALTER TABLE `state` CHANGE COLUMN `country_id` COMMENT 'Source: country_id | Physical type: STRING';

ALTER TABLE `state` CHANGE COLUMN `state_name` COMMENT 'Source: state_name | Physical type: STRING';

ALTER TABLE `supplier` CHANGE COLUMN `contact_name` COMMENT 'Source: contact_name | Physical type: STRING';

ALTER TABLE `supplier` CHANGE COLUMN `email` COMMENT 'Source: email | Physical type: STRING';

ALTER TABLE `supplier` CHANGE COLUMN `phone` COMMENT 'Source: phone | Physical type: STRING';

ALTER TABLE `supplier` CHANGE COLUMN `supplier_name` COMMENT 'Source: supplier_name | Physical type: STRING';

ALTER TABLE `warehouse` CHANGE COLUMN `city_name` COMMENT 'Source: city_name | Physical type: STRING';

ALTER TABLE `warehouse` CHANGE COLUMN `warehouse_name` COMMENT 'Source: warehouse_name | Physical type: STRING';
