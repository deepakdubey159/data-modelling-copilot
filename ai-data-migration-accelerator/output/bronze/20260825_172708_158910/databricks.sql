CREATE TABLE `dblearn`.`bronze`.`audit_log` (
  `audit_id` STRING NOT NULL,
  `operation` STRING,
  `operation_timestamp` STRING,
  `table_name` STRING,
  `user_name` STRING,
  CONSTRAINT `pk_audit_log` PRIMARY KEY (`audit_id`)
)
;

CREATE TABLE `dblearn`.`bronze`.`category` (
  `category_name` STRING NOT NULL,
  CONSTRAINT `pk_category` PRIMARY KEY (`category_name`)
)
;

CREATE TABLE `dblearn`.`bronze`.`city` (
  `city_name` STRING NOT NULL,
  `state_name` STRING NOT NULL,
  CONSTRAINT `pk_city` PRIMARY KEY (`city_name`, `state_name`)
)
CLUSTERED BY (`state_name`)
;

CREATE TABLE `dblearn`.`bronze`.`country` (
  `country_code` STRING NOT NULL,
  `country_name` STRING,
  `created_at` STRING,
  CONSTRAINT `pk_country` PRIMARY KEY (`country_code`)
)
;

CREATE TABLE `dblearn`.`bronze`.`customer` (
  `city_name` STRING,
  `credit_limit` STRING,
  `customer_number` STRING NOT NULL,
  `email` STRING,
  `first_name` STRING,
  `last_name` STRING,
  `phone` STRING,
  `status` STRING,
  CONSTRAINT `pk_customer` PRIMARY KEY (`customer_number`),
  CONSTRAINT `uq_customer_email` UNIQUE (`email`)
)
CLUSTERED BY (`customer_number`)
;

CREATE TABLE `dblearn`.`bronze`.`department` (
  `department_name` STRING NOT NULL,
  CONSTRAINT `pk_department` PRIMARY KEY (`department_name`)
)
;

CREATE TABLE `dblearn`.`bronze`.`employee` (
  `department_name` STRING,
  `email` STRING NOT NULL,
  `first_name` STRING,
  `hire_date` STRING,
  `last_name` STRING,
  `parent_email` STRING,
  `salary` DECIMAL(18,2),
  CONSTRAINT `pk_employee` PRIMARY KEY (`email`)
)
CLUSTERED BY (`email`)
;

CREATE TABLE `dblearn`.`bronze`.`inventory` (
  `quantity` BIGINT,
  `reorder_level` STRING,
  `sku` STRING NOT NULL,
  `warehouse_name` STRING NOT NULL,
  CONSTRAINT `pk_inventory` PRIMARY KEY (`warehouse_name`, `sku`),
  CONSTRAINT `ck_inventory_quantity` CHECK (quantity >= 0)
)
CLUSTERED BY (`warehouse_name`, `sku`)
;

CREATE TABLE `dblearn`.`bronze`.`order` (
  `customer_number` STRING,
  `employee_email` STRING,
  `order_date` STRING,
  `order_id` STRING NOT NULL,
  `order_status` STRING,
  CONSTRAINT `pk_order` PRIMARY KEY (`order_id`)
)
CLUSTERED BY (`order_id`)
;

CREATE TABLE `dblearn`.`bronze`.`order_item` (
  `line_number` STRING NOT NULL,
  `order_id` STRING NOT NULL,
  `product_sku` STRING,
  `quantity` BIGINT,
  `unit_price` STRING,
  CONSTRAINT `pk_order_item` PRIMARY KEY (`order_id`, `line_number`),
  CONSTRAINT `ck_order_item_quantity` CHECK (quantity >= 0)
)
CLUSTERED BY (`order_id`, `product_sku`)
;

CREATE TABLE `dblearn`.`bronze`.`payment` (
  `amount` DECIMAL(18,2),
  `order_id` STRING,
  `payment_date` STRING,
  `payment_id` STRING NOT NULL,
  `payment_method` STRING,
  CONSTRAINT `pk_payment` PRIMARY KEY (`payment_id`)
)
CLUSTERED BY (`order_id`)
;

CREATE TABLE `dblearn`.`bronze`.`product` (
  `category_name` STRING,
  `product_name` STRING,
  `sku` STRING NOT NULL,
  `status` STRING,
  `supplier_name` STRING,
  `unit_price` STRING,
  CONSTRAINT `pk_product` PRIMARY KEY (`sku`)
)
CLUSTERED BY (`sku`)
;

CREATE TABLE `dblearn`.`bronze`.`product_promotion` (
  `promotion_name` STRING NOT NULL,
  `sku` STRING NOT NULL,
  CONSTRAINT `pk_product_promotion` PRIMARY KEY (`sku`, `promotion_name`)
)
CLUSTERED BY (`sku`, `promotion_name`)
;

CREATE TABLE `dblearn`.`bronze`.`product_promotion_association` (
  `product_sku` STRING NOT NULL,
  `promotion_name` STRING NOT NULL,
  CONSTRAINT `pk_product_promotion` PRIMARY KEY (`product_sku`, `promotion_name`)
)
CLUSTERED BY (`product_sku`, `promotion_name`)
;

CREATE TABLE `dblearn`.`bronze`.`product_warehouse_association` (
  `product_sku` STRING NOT NULL,
  `warehouse_name` STRING NOT NULL,
  CONSTRAINT `pk_product_warehouse` PRIMARY KEY (`product_sku`, `warehouse_name`)
)
CLUSTERED BY (`product_sku`, `warehouse_name`)
;

CREATE TABLE `dblearn`.`bronze`.`promotion` (
  `discount_percent` STRING,
  `promotion_name` STRING NOT NULL,
  CONSTRAINT `pk_promotion` PRIMARY KEY (`promotion_name`)
)
;

CREATE TABLE `dblearn`.`bronze`.`return` (
  `order_id` STRING,
  `product_sku` STRING,
  `return_id` STRING NOT NULL,
  `return_reason` STRING,
  CONSTRAINT `pk_return` PRIMARY KEY (`return_id`)
)
CLUSTERED BY (`product_sku`, `order_id`)
;

CREATE TABLE `dblearn`.`bronze`.`shipment` (
  `order_id` STRING,
  `shipped_date` STRING,
  `tracking_number` STRING NOT NULL,
  `warehouse_name` STRING,
  CONSTRAINT `pk_shipment` PRIMARY KEY (`tracking_number`)
)
CLUSTERED BY (`warehouse_name`, `order_id`)
;

CREATE TABLE `dblearn`.`bronze`.`state` (
  `country_code` STRING NOT NULL,
  `state_name` STRING NOT NULL,
  CONSTRAINT `pk_state` PRIMARY KEY (`state_name`, `country_code`)
)
CLUSTERED BY (`country_code`)
;

CREATE TABLE `dblearn`.`bronze`.`supplier` (
  `contact_name` STRING,
  `email` STRING,
  `phone` STRING,
  `supplier_name` STRING NOT NULL,
  CONSTRAINT `pk_supplier` PRIMARY KEY (`supplier_name`),
  CONSTRAINT `uq_supplier_email` UNIQUE (`email`)
)
;

CREATE TABLE `dblearn`.`bronze`.`warehouse` (
  `city_name` STRING,
  `warehouse_name` STRING NOT NULL,
  CONSTRAINT `pk_warehouse` PRIMARY KEY (`warehouse_name`)
)
CLUSTERED BY (`warehouse_name`)
;

ALTER TABLE `dblearn`.`bronze`.`city` ADD CONSTRAINT `fk_city_state_name` FOREIGN KEY (`state_name`) REFERENCES `dblearn`.`bronze`.`state`(`state_name`);

ALTER TABLE `dblearn`.`bronze`.`customer` ADD CONSTRAINT `fk_customer_city_name` FOREIGN KEY (`city_name`) REFERENCES `dblearn`.`bronze`.`city`(`city_name`);

ALTER TABLE `dblearn`.`bronze`.`employee` ADD CONSTRAINT `fk_employee_department_name` FOREIGN KEY (`department_name`) REFERENCES `dblearn`.`bronze`.`department`(`department_name`);

ALTER TABLE `dblearn`.`bronze`.`employee` ADD CONSTRAINT `fk_employee_parent_email` FOREIGN KEY (`parent_email`) REFERENCES `dblearn`.`bronze`.`employee`(`email`);

ALTER TABLE `dblearn`.`bronze`.`inventory` ADD CONSTRAINT `fk_inventory_sku` FOREIGN KEY (`sku`) REFERENCES `dblearn`.`bronze`.`product`(`sku`);

ALTER TABLE `dblearn`.`bronze`.`inventory` ADD CONSTRAINT `fk_inventory_warehouse_name` FOREIGN KEY (`warehouse_name`) REFERENCES `dblearn`.`bronze`.`warehouse`(`warehouse_name`);

ALTER TABLE `dblearn`.`bronze`.`order` ADD CONSTRAINT `fk_order_customer_number` FOREIGN KEY (`customer_number`) REFERENCES `dblearn`.`bronze`.`customer`(`customer_number`);

ALTER TABLE `dblearn`.`bronze`.`order` ADD CONSTRAINT `fk_order_employee_email` FOREIGN KEY (`employee_email`) REFERENCES `dblearn`.`bronze`.`employee`(`email`);

ALTER TABLE `dblearn`.`bronze`.`order_item` ADD CONSTRAINT `fk_order_item_order_id` FOREIGN KEY (`order_id`) REFERENCES `dblearn`.`bronze`.`order`(`order_id`);

ALTER TABLE `dblearn`.`bronze`.`order_item` ADD CONSTRAINT `fk_order_item_product_sku` FOREIGN KEY (`product_sku`) REFERENCES `dblearn`.`bronze`.`product`(`sku`);

ALTER TABLE `dblearn`.`bronze`.`payment` ADD CONSTRAINT `fk_payment_order_id` FOREIGN KEY (`order_id`) REFERENCES `dblearn`.`bronze`.`order`(`order_id`);

ALTER TABLE `dblearn`.`bronze`.`product` ADD CONSTRAINT `fk_product_category_name` FOREIGN KEY (`category_name`) REFERENCES `dblearn`.`bronze`.`category`(`category_name`);

ALTER TABLE `dblearn`.`bronze`.`product` ADD CONSTRAINT `fk_product_supplier_name` FOREIGN KEY (`supplier_name`) REFERENCES `dblearn`.`bronze`.`supplier`(`supplier_name`);

ALTER TABLE `dblearn`.`bronze`.`product_promotion` ADD CONSTRAINT `fk_product_promotion_promotion` FOREIGN KEY (`promotion_name`) REFERENCES `dblearn`.`bronze`.`promotion`(`promotion_name`);

ALTER TABLE `dblearn`.`bronze`.`product_promotion` ADD CONSTRAINT `fk_product_promotion_sku` FOREIGN KEY (`sku`) REFERENCES `dblearn`.`bronze`.`product`(`sku`);

ALTER TABLE `dblearn`.`bronze`.`product_promotion_association` ADD CONSTRAINT `fk_product_promotion` FOREIGN KEY (`product_sku`) REFERENCES `dblearn`.`bronze`.`product`(`sku`);

ALTER TABLE `dblearn`.`bronze`.`product_promotion_association` ADD CONSTRAINT `fk_product_promotion` FOREIGN KEY (`promotion_name`) REFERENCES `dblearn`.`bronze`.`promotion`(`promotion_name`);

ALTER TABLE `dblearn`.`bronze`.`product_warehouse_association` ADD CONSTRAINT `fk_product_warehouse` FOREIGN KEY (`product_sku`) REFERENCES `dblearn`.`bronze`.`product`(`sku`);

ALTER TABLE `dblearn`.`bronze`.`product_warehouse_association` ADD CONSTRAINT `fk_product_warehouse` FOREIGN KEY (`warehouse_name`) REFERENCES `dblearn`.`bronze`.`warehouse`(`warehouse_name`);

ALTER TABLE `dblearn`.`bronze`.`return` ADD CONSTRAINT `fk_return_order_id` FOREIGN KEY (`order_id`) REFERENCES `dblearn`.`bronze`.`order`(`order_id`);

ALTER TABLE `dblearn`.`bronze`.`return` ADD CONSTRAINT `fk_return_product_sku` FOREIGN KEY (`product_sku`) REFERENCES `dblearn`.`bronze`.`product`(`sku`);

ALTER TABLE `dblearn`.`bronze`.`shipment` ADD CONSTRAINT `fk_shipment_order_id` FOREIGN KEY (`order_id`) REFERENCES `dblearn`.`bronze`.`order`(`order_id`);

ALTER TABLE `dblearn`.`bronze`.`shipment` ADD CONSTRAINT `fk_shipment_warehouse_name` FOREIGN KEY (`warehouse_name`) REFERENCES `dblearn`.`bronze`.`warehouse`(`warehouse_name`);

ALTER TABLE `dblearn`.`bronze`.`state` ADD CONSTRAINT `fk_state_country_code` FOREIGN KEY (`country_code`) REFERENCES `dblearn`.`bronze`.`country`(`country_code`);

ALTER TABLE `dblearn`.`bronze`.`warehouse` ADD CONSTRAINT `fk_warehouse_city_name` FOREIGN KEY (`city_name`) REFERENCES `dblearn`.`bronze`.`city`(`city_name`);

CREATE UNIQUE INDEX `idx_audit_log_pk` ON `dblearn`.`bronze`.`audit_log`(`audit_id`);

CREATE UNIQUE INDEX `idx_category_pk` ON `dblearn`.`bronze`.`category`(`category_name`);

CREATE UNIQUE INDEX `idx_city_pk` ON `dblearn`.`bronze`.`city`(`city_name`, `state_name`);

CREATE INDEX `idx_city_state_name` ON `dblearn`.`bronze`.`city`(`state_name`);

CREATE UNIQUE INDEX `idx_country_pk` ON `dblearn`.`bronze`.`country`(`country_code`);

CREATE INDEX `idx_customer_city_name` ON `dblearn`.`bronze`.`customer`(`city_name`);

CREATE UNIQUE INDEX `idx_customer_email` ON `dblearn`.`bronze`.`customer`(`email`);

CREATE UNIQUE INDEX `idx_customer_pk` ON `dblearn`.`bronze`.`customer`(`customer_number`);

CREATE UNIQUE INDEX `idx_department_pk` ON `dblearn`.`bronze`.`department`(`department_name`);

CREATE INDEX `idx_employee_department_name` ON `dblearn`.`bronze`.`employee`(`department_name`);

CREATE INDEX `idx_employee_parent_email` ON `dblearn`.`bronze`.`employee`(`parent_email`);

CREATE UNIQUE INDEX `idx_employee_pk` ON `dblearn`.`bronze`.`employee`(`email`);

CREATE UNIQUE INDEX `idx_inventory_pk` ON `dblearn`.`bronze`.`inventory`(`warehouse_name`, `sku`);

CREATE INDEX `idx_inventory_sku` ON `dblearn`.`bronze`.`inventory`(`sku`);

CREATE INDEX `idx_order_customer_number` ON `dblearn`.`bronze`.`order`(`customer_number`);

CREATE INDEX `idx_order_employee_email` ON `dblearn`.`bronze`.`order`(`employee_email`);

CREATE UNIQUE INDEX `idx_order_pk` ON `dblearn`.`bronze`.`order`(`order_id`);

CREATE UNIQUE INDEX `idx_order_item_pk` ON `dblearn`.`bronze`.`order_item`(`order_id`, `line_number`);

CREATE INDEX `idx_order_item_product_sku` ON `dblearn`.`bronze`.`order_item`(`product_sku`);

CREATE INDEX `idx_payment_order_id` ON `dblearn`.`bronze`.`payment`(`order_id`);

CREATE UNIQUE INDEX `idx_payment_pk` ON `dblearn`.`bronze`.`payment`(`payment_id`);

CREATE INDEX `idx_product_category_name` ON `dblearn`.`bronze`.`product`(`category_name`);

CREATE UNIQUE INDEX `idx_product_pk` ON `dblearn`.`bronze`.`product`(`sku`);

CREATE INDEX `idx_product_supplier_name` ON `dblearn`.`bronze`.`product`(`supplier_name`);

CREATE INDEX `idx_product_promotion` ON `dblearn`.`bronze`.`product_promotion`(`promotion_name`);

CREATE UNIQUE INDEX `idx_product_promotion_pk` ON `dblearn`.`bronze`.`product_promotion`(`sku`, `promotion_name`);

CREATE UNIQUE INDEX `idx_product_promotion` ON `dblearn`.`bronze`.`product_promotion_association`(`product_sku`, `promotion_name`);

CREATE INDEX `idx_product_promotion` ON `dblearn`.`bronze`.`product_promotion_association`(`promotion_name`);

CREATE UNIQUE INDEX `idx_product_warehouse` ON `dblearn`.`bronze`.`product_warehouse_association`(`product_sku`, `warehouse_name`);

CREATE INDEX `idx_product_warehouse` ON `dblearn`.`bronze`.`product_warehouse_association`(`warehouse_name`);

CREATE UNIQUE INDEX `idx_promotion_pk` ON `dblearn`.`bronze`.`promotion`(`promotion_name`);

CREATE INDEX `idx_return_order_id` ON `dblearn`.`bronze`.`return`(`order_id`);

CREATE UNIQUE INDEX `idx_return_pk` ON `dblearn`.`bronze`.`return`(`return_id`);

CREATE INDEX `idx_return_product_sku` ON `dblearn`.`bronze`.`return`(`product_sku`);

CREATE INDEX `idx_shipment_order_id` ON `dblearn`.`bronze`.`shipment`(`order_id`);

CREATE UNIQUE INDEX `idx_shipment_pk` ON `dblearn`.`bronze`.`shipment`(`tracking_number`);

CREATE INDEX `idx_shipment_warehouse_name` ON `dblearn`.`bronze`.`shipment`(`warehouse_name`);

CREATE INDEX `idx_state_country_code` ON `dblearn`.`bronze`.`state`(`country_code`);

CREATE UNIQUE INDEX `idx_state_pk` ON `dblearn`.`bronze`.`state`(`state_name`, `country_code`);

CREATE UNIQUE INDEX `idx_supplier_email` ON `dblearn`.`bronze`.`supplier`(`email`);

CREATE UNIQUE INDEX `idx_supplier_pk` ON `dblearn`.`bronze`.`supplier`(`supplier_name`);

CREATE INDEX `idx_warehouse_city_name` ON `dblearn`.`bronze`.`warehouse`(`city_name`);

CREATE UNIQUE INDEX `idx_warehouse_pk` ON `dblearn`.`bronze`.`warehouse`(`warehouse_name`);

-- Partition/Clustering Recommendation: CLUSTER BY: state_name | Rationale: Clustering on state_name co-locates rows that are joined and filtered together.

-- Partition/Clustering Recommendation: CLUSTER BY: customer_number | Rationale: Master data is looked up by key; clustering on it keeps those reads to a minimum of blocks.

-- Partition/Clustering Recommendation: CLUSTER BY: email | Rationale: Master data is looked up by key; clustering on it keeps those reads to a minimum of blocks.

-- Partition/Clustering Recommendation: CLUSTER BY: warehouse_name, sku | Rationale: Clustering on warehouse_name, sku co-locates rows that are joined and filtered together.

-- Partition/Clustering Recommendation: CLUSTER BY: order_id | Rationale: Master data is looked up by key; clustering on it keeps those reads to a minimum of blocks.

-- Partition/Clustering Recommendation: CLUSTER BY: order_id, product_sku | Rationale: Clustering on order_id, product_sku co-locates rows that are joined and filtered together.

-- Partition/Clustering Recommendation: CLUSTER BY: order_id | Rationale: Clustering on order_id co-locates rows that are joined and filtered together.

-- Partition/Clustering Recommendation: CLUSTER BY: sku | Rationale: Master data is looked up by key; clustering on it keeps those reads to a minimum of blocks.

-- Partition/Clustering Recommendation: CLUSTER BY: sku, promotion_name | Rationale: Clustering on sku, promotion_name co-locates rows that are joined and filtered together.

-- Partition/Clustering Recommendation: CLUSTER BY: product_sku, promotion_name | Rationale: Clustering on product_sku, promotion_name co-locates rows that are joined and filtered together.

-- Partition/Clustering Recommendation: CLUSTER BY: product_sku, warehouse_name | Rationale: Clustering on product_sku, warehouse_name co-locates rows that are joined and filtered together.

-- Partition/Clustering Recommendation: CLUSTER BY: product_sku, order_id | Rationale: Clustering on product_sku, order_id co-locates rows that are joined and filtered together.

-- Partition/Clustering Recommendation: CLUSTER BY: warehouse_name, order_id | Rationale: Clustering on warehouse_name, order_id co-locates rows that are joined and filtered together.

-- Partition/Clustering Recommendation: CLUSTER BY: country_code | Rationale: Clustering on country_code co-locates rows that are joined and filtered together.

-- Partition/Clustering Recommendation: CLUSTER BY: warehouse_name | Rationale: Master data is looked up by key; clustering on it keeps those reads to a minimum of blocks.

ALTER TABLE `dblearn`.`bronze`.`audit_log` CHANGE COLUMN `audit_id` COMMENT 'Source: audit_id | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`audit_log` CHANGE COLUMN `operation` COMMENT 'Source: operation | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`audit_log` CHANGE COLUMN `operation_timestamp` COMMENT 'Source: operation_timestamp | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`audit_log` CHANGE COLUMN `table_name` COMMENT 'Source: table_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`audit_log` CHANGE COLUMN `user_name` COMMENT 'Source: user_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`category` CHANGE COLUMN `category_name` COMMENT 'Source: category_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`city` CHANGE COLUMN `city_name` COMMENT 'Source: city_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`city` CHANGE COLUMN `state_name` COMMENT 'Source: state_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`country` CHANGE COLUMN `country_code` COMMENT 'Source: country_code | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`country` CHANGE COLUMN `country_name` COMMENT 'Source: country_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`country` CHANGE COLUMN `created_at` COMMENT 'Source: created_at | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`customer` CHANGE COLUMN `city_name` COMMENT 'Source: city_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`customer` CHANGE COLUMN `credit_limit` COMMENT 'Source: credit_limit | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`customer` CHANGE COLUMN `customer_number` COMMENT 'Source: customer_number | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`customer` CHANGE COLUMN `email` COMMENT 'Source: email | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`customer` CHANGE COLUMN `first_name` COMMENT 'Source: first_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`customer` CHANGE COLUMN `last_name` COMMENT 'Source: last_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`customer` CHANGE COLUMN `phone` COMMENT 'Source: phone | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`customer` CHANGE COLUMN `status` COMMENT 'Source: status | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`department` CHANGE COLUMN `department_name` COMMENT 'Source: department_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`employee` CHANGE COLUMN `department_name` COMMENT 'Source: department_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`employee` CHANGE COLUMN `email` COMMENT 'Source: email | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`employee` CHANGE COLUMN `first_name` COMMENT 'Source: first_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`employee` CHANGE COLUMN `hire_date` COMMENT 'Source: hire_date | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`employee` CHANGE COLUMN `last_name` COMMENT 'Source: last_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`employee` CHANGE COLUMN `parent_email` COMMENT 'Source: parent_email | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`employee` CHANGE COLUMN `salary` COMMENT 'Source: salary | Physical type: DECIMAL';

ALTER TABLE `dblearn`.`bronze`.`inventory` CHANGE COLUMN `quantity` COMMENT 'Source: quantity | Physical type: INTEGER';

ALTER TABLE `dblearn`.`bronze`.`inventory` CHANGE COLUMN `reorder_level` COMMENT 'Source: reorder_level | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`inventory` CHANGE COLUMN `sku` COMMENT 'Source: sku | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`inventory` CHANGE COLUMN `warehouse_name` COMMENT 'Source: warehouse_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`order` CHANGE COLUMN `customer_number` COMMENT 'Source: customer_number | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`order` CHANGE COLUMN `employee_email` COMMENT 'Source: employee_email | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`order` CHANGE COLUMN `order_date` COMMENT 'Source: order_date | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`order` CHANGE COLUMN `order_id` COMMENT 'Source: order_id | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`order` CHANGE COLUMN `order_status` COMMENT 'Source: order_status | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`order_item` CHANGE COLUMN `line_number` COMMENT 'Source: line_number | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`order_item` CHANGE COLUMN `order_id` COMMENT 'Source: order_id | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`order_item` CHANGE COLUMN `product_sku` COMMENT 'Source: product_sku | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`order_item` CHANGE COLUMN `quantity` COMMENT 'Source: quantity | Physical type: INTEGER';

ALTER TABLE `dblearn`.`bronze`.`order_item` CHANGE COLUMN `unit_price` COMMENT 'Source: unit_price | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`payment` CHANGE COLUMN `amount` COMMENT 'Source: amount | Physical type: DECIMAL';

ALTER TABLE `dblearn`.`bronze`.`payment` CHANGE COLUMN `order_id` COMMENT 'Source: order_id | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`payment` CHANGE COLUMN `payment_date` COMMENT 'Source: payment_date | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`payment` CHANGE COLUMN `payment_id` COMMENT 'Source: payment_id | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`payment` CHANGE COLUMN `payment_method` COMMENT 'Source: payment_method | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`product` CHANGE COLUMN `category_name` COMMENT 'Source: category_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`product` CHANGE COLUMN `product_name` COMMENT 'Source: product_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`product` CHANGE COLUMN `sku` COMMENT 'Source: sku | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`product` CHANGE COLUMN `status` COMMENT 'Source: status | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`product` CHANGE COLUMN `supplier_name` COMMENT 'Source: supplier_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`product` CHANGE COLUMN `unit_price` COMMENT 'Source: unit_price | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`product_promotion` CHANGE COLUMN `promotion_name` COMMENT 'Source: promotion_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`product_promotion` CHANGE COLUMN `sku` COMMENT 'Source: sku | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`product_promotion_association` CHANGE COLUMN `product_sku` COMMENT 'Source: product_sku | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`product_promotion_association` CHANGE COLUMN `promotion_name` COMMENT 'Source: promotion_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`product_warehouse_association` CHANGE COLUMN `product_sku` COMMENT 'Source: product_sku | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`product_warehouse_association` CHANGE COLUMN `warehouse_name` COMMENT 'Source: warehouse_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`promotion` CHANGE COLUMN `discount_percent` COMMENT 'Source: discount_percent | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`promotion` CHANGE COLUMN `promotion_name` COMMENT 'Source: promotion_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`return` CHANGE COLUMN `order_id` COMMENT 'Source: order_id | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`return` CHANGE COLUMN `product_sku` COMMENT 'Source: product_sku | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`return` CHANGE COLUMN `return_id` COMMENT 'Source: return_id | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`return` CHANGE COLUMN `return_reason` COMMENT 'Source: return_reason | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`shipment` CHANGE COLUMN `order_id` COMMENT 'Source: order_id | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`shipment` CHANGE COLUMN `shipped_date` COMMENT 'Source: shipped_date | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`shipment` CHANGE COLUMN `tracking_number` COMMENT 'Source: tracking_number | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`shipment` CHANGE COLUMN `warehouse_name` COMMENT 'Source: warehouse_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`state` CHANGE COLUMN `country_code` COMMENT 'Source: country_code | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`state` CHANGE COLUMN `state_name` COMMENT 'Source: state_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`supplier` CHANGE COLUMN `contact_name` COMMENT 'Source: contact_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`supplier` CHANGE COLUMN `email` COMMENT 'Source: email | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`supplier` CHANGE COLUMN `phone` COMMENT 'Source: phone | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`supplier` CHANGE COLUMN `supplier_name` COMMENT 'Source: supplier_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`warehouse` CHANGE COLUMN `city_name` COMMENT 'Source: city_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`warehouse` CHANGE COLUMN `warehouse_name` COMMENT 'Source: warehouse_name | Physical type: STRING';
