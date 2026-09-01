CREATE TABLE IF NOT EXISTS `dblearn`.`bronze`.`audit_log` (
  `audit_id` INT NOT NULL,
  `operation` STRING,
  `operation_timestamp` TIMESTAMP,
  `table_name` STRING,
  `user_name` STRING,
  CONSTRAINT `pk_audit_log` PRIMARY KEY (`audit_id`)
)
;

CREATE TABLE IF NOT EXISTS `dblearn`.`bronze`.`category` (
  `category_name` STRING NOT NULL,
  CONSTRAINT `pk_category` PRIMARY KEY (`category_name`)
)
;

CREATE TABLE IF NOT EXISTS `dblearn`.`bronze`.`city` (
  `city_name` STRING NOT NULL,
  `state_id` INT NOT NULL,
  `state_name` STRING NOT NULL,
  CONSTRAINT `pk_city` PRIMARY KEY (`city_name`, `state_id`)
)
;

CREATE TABLE IF NOT EXISTS `dblearn`.`bronze`.`country` (
  `country_code` STRING NOT NULL,
  `country_name` STRING NOT NULL,
  `created_at` TIMESTAMP,
  CONSTRAINT `pk_country` PRIMARY KEY (`country_code`)
)
;

CREATE TABLE IF NOT EXISTS `dblearn`.`bronze`.`customer` (
  `city_name` STRING,
  `credit_limit` DECIMAL(12,2),
  `customer_number` STRING NOT NULL,
  `email` STRING,
  `first_name` STRING,
  `last_name` STRING,
  `phone` STRING,
  `status` STRING,
  CONSTRAINT `pk_customer` PRIMARY KEY (`customer_number`)
)
;

CREATE TABLE IF NOT EXISTS `dblearn`.`bronze`.`department` (
  `department_name` STRING NOT NULL,
  CONSTRAINT `pk_department` PRIMARY KEY (`department_name`)
)
;

CREATE TABLE IF NOT EXISTS `dblearn`.`bronze`.`employee` (
  `department_name` STRING,
  `email` STRING NOT NULL,
  `first_name` STRING,
  `hire_date` DATE,
  `last_name` STRING,
  `parent_email` STRING,
  `salary` DECIMAL(12,2),
  CONSTRAINT `pk_employee` PRIMARY KEY (`email`)
)
;

CREATE TABLE IF NOT EXISTS `dblearn`.`bronze`.`inventory` (
  `product_id` INT NOT NULL,
  `product_sku` STRING NOT NULL,
  `quantity` INT,
  `reorder_level` INT,
  `warehouse_id` INT NOT NULL,
  `warehouse_name` STRING NOT NULL,
  CONSTRAINT `pk_inventory` PRIMARY KEY (`product_id`, `warehouse_id`)
)
;

CREATE TABLE IF NOT EXISTS `dblearn`.`bronze`.`order` (
  `customer_number` STRING,
  `employee_email` STRING,
  `order_date` DATE,
  `order_id` INT NOT NULL,
  `order_status` STRING,
  CONSTRAINT `pk_order` PRIMARY KEY (`order_id`)
)
;

CREATE TABLE IF NOT EXISTS `dblearn`.`bronze`.`order_item` (
  `line_number` INT NOT NULL,
  `order_id` INT NOT NULL,
  `product_sku` STRING,
  `quantity` INT,
  `unit_price` DECIMAL(12,2),
  CONSTRAINT `pk_order_item` PRIMARY KEY (`order_id`, `line_number`)
)
;

CREATE TABLE IF NOT EXISTS `dblearn`.`bronze`.`payment` (
  `amount` DECIMAL(12,2),
  `order_id` INT,
  `payment_date` DATE,
  `payment_id` INT NOT NULL,
  `payment_method` STRING,
  CONSTRAINT `pk_payment` PRIMARY KEY (`payment_id`)
)
;

CREATE TABLE IF NOT EXISTS `dblearn`.`bronze`.`product` (
  `category_name` STRING,
  `product_name` STRING,
  `sku` STRING NOT NULL,
  `status` STRING,
  `supplier_name` STRING,
  `unit_price` DECIMAL(12,2),
  CONSTRAINT `pk_product` PRIMARY KEY (`sku`)
)
;

CREATE TABLE IF NOT EXISTS `dblearn`.`bronze`.`product_promotion_association` (
  `product_sku` STRING NOT NULL,
  `promotion_name` STRING NOT NULL,
  CONSTRAINT `pk_product_promotion` PRIMARY KEY (`product_sku`, `promotion_name`)
)
;

CREATE TABLE IF NOT EXISTS `dblearn`.`bronze`.`product_warehouse_association` (
  `product_sku` STRING NOT NULL,
  `warehouse_name` STRING NOT NULL,
  CONSTRAINT `pk_product_warehouse` PRIMARY KEY (`product_sku`, `warehouse_name`)
)
;

CREATE TABLE IF NOT EXISTS `dblearn`.`bronze`.`promotion` (
  `discount_percent` DECIMAL(5,2),
  `promotion_name` STRING NOT NULL,
  CONSTRAINT `pk_promotion` PRIMARY KEY (`promotion_name`)
)
;

CREATE TABLE IF NOT EXISTS `dblearn`.`bronze`.`return_order` (
  `order_id` INT,
  `product_sku` STRING,
  `return_id` INT NOT NULL,
  `return_reason` STRING,
  CONSTRAINT `pk_return_order` PRIMARY KEY (`return_id`)
)
;

CREATE TABLE IF NOT EXISTS `dblearn`.`bronze`.`shipment` (
  `order_id` INT,
  `shipped_date` DATE,
  `tracking_number` STRING NOT NULL,
  `warehouse_name` STRING,
  CONSTRAINT `pk_shipment` PRIMARY KEY (`tracking_number`)
)
;

CREATE TABLE IF NOT EXISTS `dblearn`.`bronze`.`state` (
  `country_code` STRING NOT NULL,
  `country_id` INT NOT NULL,
  `state_name` STRING NOT NULL,
  CONSTRAINT `pk_state` PRIMARY KEY (`state_name`, `country_id`)
)
;

CREATE TABLE IF NOT EXISTS `dblearn`.`bronze`.`supplier` (
  `contact_name` STRING,
  `email` STRING,
  `phone` STRING,
  `supplier_name` STRING NOT NULL,
  CONSTRAINT `pk_supplier` PRIMARY KEY (`supplier_name`)
)
;

CREATE TABLE IF NOT EXISTS `dblearn`.`bronze`.`warehouse` (
  `city_name` STRING,
  `warehouse_name` STRING NOT NULL,
  CONSTRAINT `pk_warehouse` PRIMARY KEY (`warehouse_name`)
)
;

ALTER TABLE `dblearn`.`bronze`.`city` ADD CONSTRAINT `fk_city_state_state_name` FOREIGN KEY (`state_name`) REFERENCES `dblearn`.`bronze`.`state`(`state_name`);

ALTER TABLE `dblearn`.`bronze`.`customer` ADD CONSTRAINT `fk_customer_city_city_name` FOREIGN KEY (`city_name`) REFERENCES `dblearn`.`bronze`.`city`(`city_name`);

ALTER TABLE `dblearn`.`bronze`.`employee` ADD CONSTRAINT `fk_employee_department_department_name` FOREIGN KEY (`department_name`) REFERENCES `dblearn`.`bronze`.`department`(`department_name`);

ALTER TABLE `dblearn`.`bronze`.`employee` ADD CONSTRAINT `fk_employee_employee_parent_email` FOREIGN KEY (`parent_email`) REFERENCES `dblearn`.`bronze`.`employee`(`email`);

ALTER TABLE `dblearn`.`bronze`.`inventory` ADD CONSTRAINT `ck_inventory_quantity` CHECK (quantity >= 0);

ALTER TABLE `dblearn`.`bronze`.`inventory` ADD CONSTRAINT `fk_inventory_product_product_sku` FOREIGN KEY (`product_sku`) REFERENCES `dblearn`.`bronze`.`product`(`sku`);

ALTER TABLE `dblearn`.`bronze`.`inventory` ADD CONSTRAINT `fk_inventory_warehouse_warehouse_name` FOREIGN KEY (`warehouse_name`) REFERENCES `dblearn`.`bronze`.`warehouse`(`warehouse_name`);

ALTER TABLE `dblearn`.`bronze`.`order` ADD CONSTRAINT `fk_order_customer_customer_number` FOREIGN KEY (`customer_number`) REFERENCES `dblearn`.`bronze`.`customer`(`customer_number`);

ALTER TABLE `dblearn`.`bronze`.`order` ADD CONSTRAINT `fk_order_employee_employee_email` FOREIGN KEY (`employee_email`) REFERENCES `dblearn`.`bronze`.`employee`(`email`);

ALTER TABLE `dblearn`.`bronze`.`order_item` ADD CONSTRAINT `ck_order_item_quantity` CHECK (quantity >= 0);

ALTER TABLE `dblearn`.`bronze`.`order_item` ADD CONSTRAINT `fk_order_item_order_order_id` FOREIGN KEY (`order_id`) REFERENCES `dblearn`.`bronze`.`order`(`order_id`);

ALTER TABLE `dblearn`.`bronze`.`order_item` ADD CONSTRAINT `fk_order_item_product_product_sku` FOREIGN KEY (`product_sku`) REFERENCES `dblearn`.`bronze`.`product`(`sku`);

ALTER TABLE `dblearn`.`bronze`.`payment` ADD CONSTRAINT `fk_payment_order_order_id` FOREIGN KEY (`order_id`) REFERENCES `dblearn`.`bronze`.`order`(`order_id`);

ALTER TABLE `dblearn`.`bronze`.`product` ADD CONSTRAINT `fk_product_category_category_name` FOREIGN KEY (`category_name`) REFERENCES `dblearn`.`bronze`.`category`(`category_name`);

ALTER TABLE `dblearn`.`bronze`.`product` ADD CONSTRAINT `fk_product_supplier_supplier_name` FOREIGN KEY (`supplier_name`) REFERENCES `dblearn`.`bronze`.`supplier`(`supplier_name`);

ALTER TABLE `dblearn`.`bronze`.`product_promotion_association` ADD CONSTRAINT `fk_product_promotion_association_product_product_sku` FOREIGN KEY (`product_sku`) REFERENCES `dblearn`.`bronze`.`product`(`sku`);

ALTER TABLE `dblearn`.`bronze`.`product_promotion_association` ADD CONSTRAINT `fk_product_promotion_association_promotion_promotion_name` FOREIGN KEY (`promotion_name`) REFERENCES `dblearn`.`bronze`.`promotion`(`promotion_name`);

ALTER TABLE `dblearn`.`bronze`.`product_warehouse_association` ADD CONSTRAINT `fk_product_warehouse_association_product_product_sku` FOREIGN KEY (`product_sku`) REFERENCES `dblearn`.`bronze`.`product`(`sku`);

ALTER TABLE `dblearn`.`bronze`.`product_warehouse_association` ADD CONSTRAINT `fk_product_warehouse_association_warehouse_warehouse_name` FOREIGN KEY (`warehouse_name`) REFERENCES `dblearn`.`bronze`.`warehouse`(`warehouse_name`);

ALTER TABLE `dblearn`.`bronze`.`promotion` ADD CONSTRAINT `ck_promotion_discount_percent` CHECK (discount_percent BETWEEN 0 AND 100);

ALTER TABLE `dblearn`.`bronze`.`return_order` ADD CONSTRAINT `fk_return_order_order_order_id` FOREIGN KEY (`order_id`) REFERENCES `dblearn`.`bronze`.`order`(`order_id`);

ALTER TABLE `dblearn`.`bronze`.`return_order` ADD CONSTRAINT `fk_return_order_product_product_sku` FOREIGN KEY (`product_sku`) REFERENCES `dblearn`.`bronze`.`product`(`sku`);

ALTER TABLE `dblearn`.`bronze`.`shipment` ADD CONSTRAINT `fk_shipment_order_order_id` FOREIGN KEY (`order_id`) REFERENCES `dblearn`.`bronze`.`order`(`order_id`);

ALTER TABLE `dblearn`.`bronze`.`shipment` ADD CONSTRAINT `fk_shipment_warehouse_warehouse_name` FOREIGN KEY (`warehouse_name`) REFERENCES `dblearn`.`bronze`.`warehouse`(`warehouse_name`);

ALTER TABLE `dblearn`.`bronze`.`state` ADD CONSTRAINT `fk_state_country_country_code` FOREIGN KEY (`country_code`) REFERENCES `dblearn`.`bronze`.`country`(`country_code`);

ALTER TABLE `dblearn`.`bronze`.`warehouse` ADD CONSTRAINT `fk_warehouse_city_city_name` FOREIGN KEY (`city_name`) REFERENCES `dblearn`.`bronze`.`city`(`city_name`);

-- Index recommendation (idx_audit_log_pk): UNIQUE INDEX on `dblearn`.`bronze`.`audit_log`(audit_id) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces and serves lookups on the primary key.

-- Index recommendation (idx_category_pk): UNIQUE INDEX on `dblearn`.`bronze`.`category`(category_name) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces and serves lookups on the primary key.

-- Index recommendation (idx_city_pk): UNIQUE INDEX on `dblearn`.`bronze`.`city`(city_name, state_id) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces and serves lookups on the primary key.

-- Index recommendation (idx_city_state_name): INDEX on `dblearn`.`bronze`.`city`(state_name) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Foreign keys are joined on constantly and are scanned when the parent is deleted; an unindexed foreign key is a common cause of slow joins and lock escalation.

-- Index recommendation (idx_country_pk): UNIQUE INDEX on `dblearn`.`bronze`.`country`(country_code) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces and serves lookups on the primary key.

-- Index recommendation (idx_customer_city_name): INDEX on `dblearn`.`bronze`.`customer`(city_name) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Foreign keys are joined on constantly and are scanned when the parent is deleted; an unindexed foreign key is a common cause of slow joins and lock escalation.

-- Index recommendation (idx_customer_email): UNIQUE INDEX on `dblearn`.`bronze`.`customer`(email) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces the alternate key.

-- Index recommendation (idx_customer_pk): UNIQUE INDEX on `dblearn`.`bronze`.`customer`(customer_number) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces and serves lookups on the primary key.

-- Index recommendation (idx_department_pk): UNIQUE INDEX on `dblearn`.`bronze`.`department`(department_name) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces and serves lookups on the primary key.

-- Index recommendation (idx_employee_department_name): INDEX on `dblearn`.`bronze`.`employee`(department_name) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Foreign keys are joined on constantly and are scanned when the parent is deleted; an unindexed foreign key is a common cause of slow joins and lock escalation.

-- Index recommendation (idx_employee_parent_email): INDEX on `dblearn`.`bronze`.`employee`(parent_email) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Foreign keys are joined on constantly and are scanned when the parent is deleted; an unindexed foreign key is a common cause of slow joins and lock escalation.

-- Index recommendation (idx_employee_pk): UNIQUE INDEX on `dblearn`.`bronze`.`employee`(email) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces and serves lookups on the primary key.

-- Index recommendation (idx_inventory_pk): UNIQUE INDEX on `dblearn`.`bronze`.`inventory`(product_id, warehouse_id) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces and serves lookups on the primary key.

-- Index recommendation (idx_inventory_product_sku): INDEX on `dblearn`.`bronze`.`inventory`(product_sku) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Foreign keys are joined on constantly and are scanned when the parent is deleted; an unindexed foreign key is a common cause of slow joins and lock escalation.

-- Index recommendation (idx_inventory_warehouse_name): INDEX on `dblearn`.`bronze`.`inventory`(warehouse_name) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Foreign keys are joined on constantly and are scanned when the parent is deleted; an unindexed foreign key is a common cause of slow joins and lock escalation.

-- Index recommendation (idx_order_customer_number): INDEX on `dblearn`.`bronze`.`order`(customer_number) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Foreign keys are joined on constantly and are scanned when the parent is deleted; an unindexed foreign key is a common cause of slow joins and lock escalation.

-- Index recommendation (idx_order_employee_email): INDEX on `dblearn`.`bronze`.`order`(employee_email) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Foreign keys are joined on constantly and are scanned when the parent is deleted; an unindexed foreign key is a common cause of slow joins and lock escalation.

-- Index recommendation (idx_order_pk): UNIQUE INDEX on `dblearn`.`bronze`.`order`(order_id) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces and serves lookups on the primary key.

-- Index recommendation (idx_order_item_pk): UNIQUE INDEX on `dblearn`.`bronze`.`order_item`(order_id, line_number) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces and serves lookups on the primary key.

-- Index recommendation (idx_order_item_product_sku): INDEX on `dblearn`.`bronze`.`order_item`(product_sku) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Foreign keys are joined on constantly and are scanned when the parent is deleted; an unindexed foreign key is a common cause of slow joins and lock escalation.

-- Index recommendation (idx_payment_order_id): INDEX on `dblearn`.`bronze`.`payment`(order_id) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Foreign keys are joined on constantly and are scanned when the parent is deleted; an unindexed foreign key is a common cause of slow joins and lock escalation.

-- Index recommendation (idx_payment_pk): UNIQUE INDEX on `dblearn`.`bronze`.`payment`(payment_id) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces and serves lookups on the primary key.

-- Index recommendation (idx_product_category_name): INDEX on `dblearn`.`bronze`.`product`(category_name) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Foreign keys are joined on constantly and are scanned when the parent is deleted; an unindexed foreign key is a common cause of slow joins and lock escalation.

-- Index recommendation (idx_product_pk): UNIQUE INDEX on `dblearn`.`bronze`.`product`(sku) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces and serves lookups on the primary key.

-- Index recommendation (idx_product_supplier_name): INDEX on `dblearn`.`bronze`.`product`(supplier_name) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Foreign keys are joined on constantly and are scanned when the parent is deleted; an unindexed foreign key is a common cause of slow joins and lock escalation.

-- Index recommendation (idx_product_promotion): UNIQUE INDEX on `dblearn`.`bronze`.`product_promotion_association`(product_sku, promotion_name) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces and serves lookups on the primary key.

-- Index recommendation (idx_product_promotion): INDEX on `dblearn`.`bronze`.`product_promotion_association`(promotion_name) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Foreign keys are joined on constantly and are scanned when the parent is deleted; an unindexed foreign key is a common cause of slow joins and lock escalation.

-- Index recommendation (idx_product_warehouse): UNIQUE INDEX on `dblearn`.`bronze`.`product_warehouse_association`(product_sku, warehouse_name) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces and serves lookups on the primary key.

-- Index recommendation (idx_product_warehouse): INDEX on `dblearn`.`bronze`.`product_warehouse_association`(warehouse_name) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Foreign keys are joined on constantly and are scanned when the parent is deleted; an unindexed foreign key is a common cause of slow joins and lock escalation.

-- Index recommendation (idx_promotion_pk): UNIQUE INDEX on `dblearn`.`bronze`.`promotion`(promotion_name) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces and serves lookups on the primary key.

-- Index recommendation (idx_return_order_order_id): INDEX on `dblearn`.`bronze`.`return_order`(order_id) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Foreign keys are joined on constantly and are scanned when the parent is deleted; an unindexed foreign key is a common cause of slow joins and lock escalation.

-- Index recommendation (idx_return_order_pk): UNIQUE INDEX on `dblearn`.`bronze`.`return_order`(return_id) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces and serves lookups on the primary key.

-- Index recommendation (idx_return_order_product_sku): INDEX on `dblearn`.`bronze`.`return_order`(product_sku) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Foreign keys are joined on constantly and are scanned when the parent is deleted; an unindexed foreign key is a common cause of slow joins and lock escalation.

-- Index recommendation (idx_shipment_order_id): INDEX on `dblearn`.`bronze`.`shipment`(order_id) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Foreign keys are joined on constantly and are scanned when the parent is deleted; an unindexed foreign key is a common cause of slow joins and lock escalation.

-- Index recommendation (idx_shipment_pk): UNIQUE INDEX on `dblearn`.`bronze`.`shipment`(tracking_number) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces and serves lookups on the primary key.

-- Index recommendation (idx_shipment_warehouse_name): INDEX on `dblearn`.`bronze`.`shipment`(warehouse_name) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Foreign keys are joined on constantly and are scanned when the parent is deleted; an unindexed foreign key is a common cause of slow joins and lock escalation.

-- Index recommendation (idx_state_country_code): INDEX on `dblearn`.`bronze`.`state`(country_code) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Foreign keys are joined on constantly and are scanned when the parent is deleted; an unindexed foreign key is a common cause of slow joins and lock escalation.

-- Index recommendation (idx_state_pk): UNIQUE INDEX on `dblearn`.`bronze`.`state`(state_name, country_id) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces and serves lookups on the primary key.

-- Index recommendation (idx_supplier_email): UNIQUE INDEX on `dblearn`.`bronze`.`supplier`(email) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces the alternate key.

-- Index recommendation (idx_supplier_pk): UNIQUE INDEX on `dblearn`.`bronze`.`supplier`(supplier_name) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces and serves lookups on the primary key.

-- Index recommendation (idx_warehouse_city_name): INDEX on `dblearn`.`bronze`.`warehouse`(city_name) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Foreign keys are joined on constantly and are scanned when the parent is deleted; an unindexed foreign key is a common cause of slow joins and lock escalation.

-- Index recommendation (idx_warehouse_pk): UNIQUE INDEX on `dblearn`.`bronze`.`warehouse`(warehouse_name) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces and serves lookups on the primary key.

-- Partition/Clustering Recommendation: PARTITION BY: operation_timestamp | Rationale: Transaction volume accumulates over time, so partitioning on operation_timestamp lets queries prune to a date range.

-- Partition/Clustering Recommendation: CLUSTER BY: city_name, state_id | Rationale: Master data is looked up by key; clustering on it keeps those reads to a minimum of blocks.

-- Partition/Clustering Recommendation: CLUSTER BY: customer_number | Rationale: Master data is looked up by key; clustering on it keeps those reads to a minimum of blocks.

-- Partition/Clustering Recommendation: CLUSTER BY: email | Rationale: Master data is looked up by key; clustering on it keeps those reads to a minimum of blocks.

-- Partition/Clustering Recommendation: CLUSTER BY: product_sku, warehouse_name | Rationale: Clustering on product_sku, warehouse_name co-locates rows that are joined and filtered together.

-- Partition/Clustering Recommendation: PARTITION BY: order_date | CLUSTER BY: employee_email, customer_number | Rationale: Transaction volume accumulates over time, so partitioning on order_date lets queries prune to a date range. Clustering on employee_email, customer_number co-locates rows that are joined and filtered together.

-- Partition/Clustering Recommendation: CLUSTER BY: order_id, product_sku | Rationale: Clustering on order_id, product_sku co-locates rows that are joined and filtered together.

-- Partition/Clustering Recommendation: PARTITION BY: payment_date | CLUSTER BY: order_id | Rationale: Transaction volume accumulates over time, so partitioning on payment_date lets queries prune to a date range. Clustering on order_id co-locates rows that are joined and filtered together.

-- Partition/Clustering Recommendation: CLUSTER BY: sku | Rationale: Master data is looked up by key; clustering on it keeps those reads to a minimum of blocks.

-- Partition/Clustering Recommendation: CLUSTER BY: product_sku, promotion_name | Rationale: Clustering on product_sku, promotion_name co-locates rows that are joined and filtered together.

-- Partition/Clustering Recommendation: CLUSTER BY: product_sku, warehouse_name | Rationale: Clustering on product_sku, warehouse_name co-locates rows that are joined and filtered together.

-- Partition/Clustering Recommendation: CLUSTER BY: product_sku, order_id | Rationale: Clustering on product_sku, order_id co-locates rows that are joined and filtered together.

-- Partition/Clustering Recommendation: PARTITION BY: shipped_date | CLUSTER BY: warehouse_name, order_id | Rationale: Transaction volume accumulates over time, so partitioning on shipped_date lets queries prune to a date range. Clustering on warehouse_name, order_id co-locates rows that are joined and filtered together.

-- Partition/Clustering Recommendation: CLUSTER BY: state_name, country_id | Rationale: Master data is looked up by key; clustering on it keeps those reads to a minimum of blocks.

-- Partition/Clustering Recommendation: CLUSTER BY: warehouse_name | Rationale: Master data is looked up by key; clustering on it keeps those reads to a minimum of blocks.

ALTER TABLE `dblearn`.`bronze`.`audit_log` CHANGE COLUMN `audit_id` COMMENT 'Source: audit_id | Physical type: INTEGER';

ALTER TABLE `dblearn`.`bronze`.`audit_log` CHANGE COLUMN `operation` COMMENT 'Source: operation | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`audit_log` CHANGE COLUMN `operation_timestamp` COMMENT 'Source: operation_timestamp | Physical type: TIMESTAMP';

ALTER TABLE `dblearn`.`bronze`.`audit_log` CHANGE COLUMN `table_name` COMMENT 'Source: table_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`audit_log` CHANGE COLUMN `user_name` COMMENT 'Source: user_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`category` CHANGE COLUMN `category_name` COMMENT 'Source: category_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`city` CHANGE COLUMN `city_name` COMMENT 'Source: city_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`city` CHANGE COLUMN `state_id` COMMENT 'Source: state_id | Physical type: INTEGER';

ALTER TABLE `dblearn`.`bronze`.`city` CHANGE COLUMN `state_name` COMMENT 'Source: state_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`country` CHANGE COLUMN `country_code` COMMENT 'Source: country_code | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`country` CHANGE COLUMN `country_name` COMMENT 'Source: country_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`country` CHANGE COLUMN `created_at` COMMENT 'Source: created_at | Physical type: TIMESTAMP';

ALTER TABLE `dblearn`.`bronze`.`customer` CHANGE COLUMN `city_name` COMMENT 'Source: city_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`customer` CHANGE COLUMN `credit_limit` COMMENT 'Source: credit_limit | Physical type: DECIMAL';

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

ALTER TABLE `dblearn`.`bronze`.`employee` CHANGE COLUMN `hire_date` COMMENT 'Source: hire_date | Physical type: DATE';

ALTER TABLE `dblearn`.`bronze`.`employee` CHANGE COLUMN `last_name` COMMENT 'Source: last_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`employee` CHANGE COLUMN `parent_email` COMMENT 'Source: parent_email | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`employee` CHANGE COLUMN `salary` COMMENT 'Source: salary | Physical type: DECIMAL';

ALTER TABLE `dblearn`.`bronze`.`inventory` CHANGE COLUMN `product_id` COMMENT 'Source: product_id | Physical type: INTEGER';

ALTER TABLE `dblearn`.`bronze`.`inventory` CHANGE COLUMN `product_sku` COMMENT 'Source: product_sku | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`inventory` CHANGE COLUMN `quantity` COMMENT 'Source: quantity | Physical type: INTEGER';

ALTER TABLE `dblearn`.`bronze`.`inventory` CHANGE COLUMN `reorder_level` COMMENT 'Source: reorder_level | Physical type: INTEGER';

ALTER TABLE `dblearn`.`bronze`.`inventory` CHANGE COLUMN `warehouse_id` COMMENT 'Source: warehouse_id | Physical type: INTEGER';

ALTER TABLE `dblearn`.`bronze`.`inventory` CHANGE COLUMN `warehouse_name` COMMENT 'Source: warehouse_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`order` CHANGE COLUMN `customer_number` COMMENT 'Source: customer_number | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`order` CHANGE COLUMN `employee_email` COMMENT 'Source: employee_email | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`order` CHANGE COLUMN `order_date` COMMENT 'Source: order_date | Physical type: DATE';

ALTER TABLE `dblearn`.`bronze`.`order` CHANGE COLUMN `order_id` COMMENT 'Source: order_id | Physical type: INTEGER';

ALTER TABLE `dblearn`.`bronze`.`order` CHANGE COLUMN `order_status` COMMENT 'Source: order_status | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`order_item` CHANGE COLUMN `line_number` COMMENT 'Source: line_number | Physical type: INTEGER';

ALTER TABLE `dblearn`.`bronze`.`order_item` CHANGE COLUMN `order_id` COMMENT 'Source: order_id | Physical type: INTEGER';

ALTER TABLE `dblearn`.`bronze`.`order_item` CHANGE COLUMN `product_sku` COMMENT 'Source: product_sku | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`order_item` CHANGE COLUMN `quantity` COMMENT 'Source: quantity | Physical type: INTEGER';

ALTER TABLE `dblearn`.`bronze`.`order_item` CHANGE COLUMN `unit_price` COMMENT 'Source: unit_price | Physical type: DECIMAL';

ALTER TABLE `dblearn`.`bronze`.`payment` CHANGE COLUMN `amount` COMMENT 'Source: amount | Physical type: DECIMAL';

ALTER TABLE `dblearn`.`bronze`.`payment` CHANGE COLUMN `order_id` COMMENT 'Source: order_id | Physical type: INTEGER';

ALTER TABLE `dblearn`.`bronze`.`payment` CHANGE COLUMN `payment_date` COMMENT 'Source: payment_date | Physical type: DATE';

ALTER TABLE `dblearn`.`bronze`.`payment` CHANGE COLUMN `payment_id` COMMENT 'Source: payment_id | Physical type: INTEGER';

ALTER TABLE `dblearn`.`bronze`.`payment` CHANGE COLUMN `payment_method` COMMENT 'Source: payment_method | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`product` CHANGE COLUMN `category_name` COMMENT 'Source: category_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`product` CHANGE COLUMN `product_name` COMMENT 'Source: product_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`product` CHANGE COLUMN `sku` COMMENT 'Source: sku | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`product` CHANGE COLUMN `status` COMMENT 'Source: status | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`product` CHANGE COLUMN `supplier_name` COMMENT 'Source: supplier_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`product` CHANGE COLUMN `unit_price` COMMENT 'Source: unit_price | Physical type: DECIMAL';

ALTER TABLE `dblearn`.`bronze`.`product_promotion_association` CHANGE COLUMN `product_sku` COMMENT 'Source: product_sku | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`product_promotion_association` CHANGE COLUMN `promotion_name` COMMENT 'Source: promotion_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`product_warehouse_association` CHANGE COLUMN `product_sku` COMMENT 'Source: product_sku | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`product_warehouse_association` CHANGE COLUMN `warehouse_name` COMMENT 'Source: warehouse_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`promotion` CHANGE COLUMN `discount_percent` COMMENT 'Source: discount_percent | Physical type: DECIMAL';

ALTER TABLE `dblearn`.`bronze`.`promotion` CHANGE COLUMN `promotion_name` COMMENT 'Source: promotion_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`return_order` CHANGE COLUMN `order_id` COMMENT 'Source: order_id | Physical type: INTEGER';

ALTER TABLE `dblearn`.`bronze`.`return_order` CHANGE COLUMN `product_sku` COMMENT 'Source: product_sku | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`return_order` CHANGE COLUMN `return_id` COMMENT 'Source: return_id | Physical type: INTEGER';

ALTER TABLE `dblearn`.`bronze`.`return_order` CHANGE COLUMN `return_reason` COMMENT 'Source: return_reason | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`shipment` CHANGE COLUMN `order_id` COMMENT 'Source: order_id | Physical type: INTEGER';

ALTER TABLE `dblearn`.`bronze`.`shipment` CHANGE COLUMN `shipped_date` COMMENT 'Source: shipped_date | Physical type: DATE';

ALTER TABLE `dblearn`.`bronze`.`shipment` CHANGE COLUMN `tracking_number` COMMENT 'Source: tracking_number | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`shipment` CHANGE COLUMN `warehouse_name` COMMENT 'Source: warehouse_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`state` CHANGE COLUMN `country_code` COMMENT 'Source: country_code | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`state` CHANGE COLUMN `country_id` COMMENT 'Source: country_id | Physical type: INTEGER';

ALTER TABLE `dblearn`.`bronze`.`state` CHANGE COLUMN `state_name` COMMENT 'Source: state_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`supplier` CHANGE COLUMN `contact_name` COMMENT 'Source: contact_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`supplier` CHANGE COLUMN `email` COMMENT 'Source: email | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`supplier` CHANGE COLUMN `phone` COMMENT 'Source: phone | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`supplier` CHANGE COLUMN `supplier_name` COMMENT 'Source: supplier_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`warehouse` CHANGE COLUMN `city_name` COMMENT 'Source: city_name | Physical type: STRING';

ALTER TABLE `dblearn`.`bronze`.`warehouse` CHANGE COLUMN `warehouse_name` COMMENT 'Source: warehouse_name | Physical type: STRING';
