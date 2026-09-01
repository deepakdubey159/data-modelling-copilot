CREATE TABLE IF NOT EXISTS `dblearn`.`bronze`.`customer` (
  `city` STRING COMMENT 'Source: city | Physical type: STRING',
  `country` STRING COMMENT 'Source: country | Physical type: STRING',
  `credit_limit` DECIMAL(12,2) COMMENT 'Source: credit_limit | Physical type: DECIMAL',
  `customer_code` STRING NOT NULL COMMENT 'Source: customer_code | Physical type: STRING',
  `customer_status` STRING COMMENT 'Source: customer_status | Physical type: STRING',
  `date_of_birth` DATE COMMENT 'Source: date_of_birth | Physical type: DATE',
  `email` STRING COMMENT 'Source: email | Physical type: STRING',
  `first_name` STRING NOT NULL COMMENT 'Source: first_name | Physical type: STRING',
  `gender` STRING COMMENT 'Source: gender | Physical type: STRING',
  `is_active` BOOLEAN COMMENT 'Source: is_active | Physical type: BOOLEAN',
  `last_name` STRING COMMENT 'Source: last_name | Physical type: STRING',
  `phone_number` STRING COMMENT 'Source: phone_number | Physical type: STRING',
  `postal_code` STRING COMMENT 'Source: postal_code | Physical type: STRING',
  `state` STRING COMMENT 'Source: state | Physical type: STRING',
  CONSTRAINT `pk_customer` PRIMARY KEY (`customer_code`)
)
;

CREATE TABLE IF NOT EXISTS `dblearn`.`bronze`.`order` (
  `created_by` STRING COMMENT 'Source: created_by | Physical type: STRING',
  `created_date` TIMESTAMP COMMENT 'Source: created_date | Physical type: TIMESTAMP',
  `customer_code` STRING NOT NULL COMMENT 'Source: customer_code | Physical type: STRING',
  `discount_amount` DECIMAL(12,2) COMMENT 'Source: discount_amount | Physical type: DECIMAL',
  `order_date` TIMESTAMP COMMENT 'Source: order_date | Physical type: TIMESTAMP',
  `order_number` STRING NOT NULL COMMENT 'Source: order_number | Physical type: STRING',
  `order_status` STRING COMMENT 'Source: order_status | Physical type: STRING',
  `payment_method` STRING COMMENT 'Source: payment_method | Physical type: STRING',
  `remarks` STRING COMMENT 'Source: remarks | Physical type: STRING',
  `shipped_date` TIMESTAMP COMMENT 'Source: shipped_date | Physical type: TIMESTAMP',
  `shipping_amount` DECIMAL(12,2) COMMENT 'Source: shipping_amount | Physical type: DECIMAL',
  `tax_amount` DECIMAL(12,2) COMMENT 'Source: tax_amount | Physical type: DECIMAL',
  `total_amount` DECIMAL(12,2) COMMENT 'Source: total_amount | Physical type: DECIMAL',
  CONSTRAINT `pk_order` PRIMARY KEY (`order_number`)
)
;

CREATE TABLE IF NOT EXISTS `dblearn`.`bronze`.`order_item` (
  `order_item_id` BIGINT NOT NULL COMMENT 'Source: order_item_id | Physical type: INTEGER',
  `order_number` STRING NOT NULL COMMENT 'Source: order_number | Physical type: STRING',
  `product_name` STRING COMMENT 'Source: product_name | Physical type: STRING',
  `quantity` INT NOT NULL COMMENT 'Source: quantity | Physical type: INTEGER',
  `total_price` DECIMAL(12,2) COMMENT 'Source: total_price | Physical type: DECIMAL',
  `unit_price` DECIMAL(10,2) COMMENT 'Source: unit_price | Physical type: DECIMAL',
  CONSTRAINT `pk_order_item` PRIMARY KEY (`order_item_id`)
)
;

CREATE TABLE IF NOT EXISTS `dblearn`.`bronze`.`order_line_item` (
  `order_id` BIGINT NOT NULL COMMENT 'Source: order_id | Physical type: INTEGER',
  `product_name` STRING NOT NULL COMMENT 'Source: product_name | Physical type: STRING',
  `quantity` INT NOT NULL COMMENT 'Source: quantity | Physical type: INTEGER',
  `total_price` DECIMAL(12,2) COMMENT 'Source: total_price | Physical type: DECIMAL',
  `unit_price` DECIMAL(10,2) COMMENT 'Source: unit_price | Physical type: DECIMAL',
  CONSTRAINT `pk_order_line_item` PRIMARY KEY (`order_id`, `product_name`)
)
;

CREATE TABLE IF NOT EXISTS `dblearn`.`bronze`.`order_product` (
  `order_id` BIGINT NOT NULL COMMENT 'Source: order_id | Physical type: INTEGER',
  `order_number` STRING NOT NULL COMMENT 'Source: order_number | Physical type: STRING',
  `product_code` STRING NOT NULL COMMENT 'Source: product_code | Physical type: STRING',
  `product_id` BIGINT NOT NULL COMMENT 'Source: product_id | Physical type: INTEGER',
  `quantity` INT COMMENT 'Source: quantity | Physical type: INTEGER',
  `selling_price` DECIMAL(10,2) COMMENT 'Source: selling_price | Physical type: DECIMAL',
  CONSTRAINT `pk_order_product` PRIMARY KEY (`order_id`, `product_id`)
)
;

CREATE TABLE IF NOT EXISTS `dblearn`.`bronze`.`order_product_association` (
  `order_number` STRING NOT NULL COMMENT 'Source: order_number | Physical type: STRING',
  `product_code` STRING NOT NULL COMMENT 'Source: product_code | Physical type: STRING',
  CONSTRAINT `pk_order_product_association` PRIMARY KEY (`order_number`, `product_code`)
)
;

CREATE TABLE IF NOT EXISTS `dblearn`.`bronze`.`product` (
  `category` STRING COMMENT 'Source: category | Physical type: STRING',
  `created_date` TIMESTAMP COMMENT 'Source: created_date | Physical type: TIMESTAMP',
  `is_active` BOOLEAN COMMENT 'Source: is_active | Physical type: BOOLEAN',
  `price` DECIMAL(10,2) COMMENT 'Source: price | Physical type: DECIMAL',
  `product_code` STRING NOT NULL COMMENT 'Source: product_code | Physical type: STRING',
  `product_name` STRING COMMENT 'Source: product_name | Physical type: STRING',
  `stock_quantity` INT COMMENT 'Source: stock_quantity | Physical type: INTEGER',
  `supplier_name` STRING COMMENT 'Source: supplier_name | Physical type: STRING',
  CONSTRAINT `pk_product` PRIMARY KEY (`product_code`)
)
;

ALTER TABLE `dblearn`.`bronze`.`order` ADD CONSTRAINT `fk_order_customer_customer_code` FOREIGN KEY (`customer_code`) REFERENCES `dblearn`.`bronze`.`customer`(`customer_code`);

ALTER TABLE `dblearn`.`bronze`.`order_item` ADD CONSTRAINT `ck_order_item_quantity` CHECK (quantity >= 0);

ALTER TABLE `dblearn`.`bronze`.`order_item` ADD CONSTRAINT `fk_order_item_order_order_number` FOREIGN KEY (`order_number`) REFERENCES `dblearn`.`bronze`.`order`(`order_number`);

ALTER TABLE `dblearn`.`bronze`.`order_line_item` ADD CONSTRAINT `ck_order_line_item_quantity` CHECK (quantity >= 0);

ALTER TABLE `dblearn`.`bronze`.`order_product` ADD CONSTRAINT `ck_order_product_quantity` CHECK (quantity >= 0);

ALTER TABLE `dblearn`.`bronze`.`order_product` ADD CONSTRAINT `fk_order_product_order_order_number` FOREIGN KEY (`order_number`) REFERENCES `dblearn`.`bronze`.`order`(`order_number`);

ALTER TABLE `dblearn`.`bronze`.`order_product` ADD CONSTRAINT `fk_order_product_product_product_code` FOREIGN KEY (`product_code`) REFERENCES `dblearn`.`bronze`.`product`(`product_code`);

ALTER TABLE `dblearn`.`bronze`.`order_product_association` ADD CONSTRAINT `fk_order_product_association_order_order_number` FOREIGN KEY (`order_number`) REFERENCES `dblearn`.`bronze`.`order`(`order_number`);

ALTER TABLE `dblearn`.`bronze`.`order_product_association` ADD CONSTRAINT `fk_order_product_association_product_product_code` FOREIGN KEY (`product_code`) REFERENCES `dblearn`.`bronze`.`product`(`product_code`);

-- Index recommendation (idx_customer_email): UNIQUE INDEX on `dblearn`.`bronze`.`customer`(email) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces the alternate key.

-- Index recommendation (idx_customer_phone_number): UNIQUE INDEX on `dblearn`.`bronze`.`customer`(phone_number) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces the alternate key.

-- Index recommendation (idx_customer_pk): UNIQUE INDEX on `dblearn`.`bronze`.`customer`(customer_code) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces and serves lookups on the primary key.

-- Index recommendation (idx_customer_postal_code): UNIQUE INDEX on `dblearn`.`bronze`.`customer`(postal_code) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces the alternate key.

-- Index recommendation (idx_order_customer_code): INDEX on `dblearn`.`bronze`.`order`(customer_code) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Foreign keys are joined on constantly and are scanned when the parent is deleted; an unindexed foreign key is a common cause of slow joins and lock escalation.

-- Index recommendation (idx_order_pk): UNIQUE INDEX on `dblearn`.`bronze`.`order`(order_number) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces and serves lookups on the primary key.

-- Index recommendation (idx_order_item_order_number): INDEX on `dblearn`.`bronze`.`order_item`(order_number) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Foreign keys are joined on constantly and are scanned when the parent is deleted; an unindexed foreign key is a common cause of slow joins and lock escalation.

-- Index recommendation (idx_order_item_pk): UNIQUE INDEX on `dblearn`.`bronze`.`order_item`(order_item_id) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces and serves lookups on the primary key.

-- Index recommendation (idx_order_line_item_pk): UNIQUE INDEX on `dblearn`.`bronze`.`order_line_item`(order_id, product_name) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces and serves lookups on the primary key.

-- Index recommendation (idx_order_product_order_number): INDEX on `dblearn`.`bronze`.`order_product`(order_number) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Foreign keys are joined on constantly and are scanned when the parent is deleted; an unindexed foreign key is a common cause of slow joins and lock escalation.

-- Index recommendation (idx_order_product_pk): UNIQUE INDEX on `dblearn`.`bronze`.`order_product`(order_id, product_id) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces and serves lookups on the primary key.

-- Index recommendation (idx_order_product_product_code): INDEX on `dblearn`.`bronze`.`order_product`(product_code) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Foreign keys are joined on constantly and are scanned when the parent is deleted; an unindexed foreign key is a common cause of slow joins and lock escalation.

-- Index recommendation (idx_order_product_association): UNIQUE INDEX on `dblearn`.`bronze`.`order_product_association`(order_number, product_code) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces and serves lookups on the primary key.

-- Index recommendation (idx_order_product_association): INDEX on `dblearn`.`bronze`.`order_product_association`(product_code) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Foreign keys are joined on constantly and are scanned when the parent is deleted; an unindexed foreign key is a common cause of slow joins and lock escalation.

-- Index recommendation (idx_product_pk): UNIQUE INDEX on `dblearn`.`bronze`.`product`(product_code) - Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated column instead | Enforces and serves lookups on the primary key.

-- Partition/Clustering Recommendation: CLUSTER BY: order_number | Rationale: Master data is looked up by key; clustering on it keeps those reads to a minimum of blocks.

-- Partition/Clustering Recommendation: CLUSTER BY: order_number | Rationale: Clustering on order_number co-locates rows that are joined and filtered together.

-- Partition/Clustering Recommendation: CLUSTER BY: product_code, order_number | Rationale: Clustering on product_code, order_number co-locates rows that are joined and filtered together.

-- Partition/Clustering Recommendation: CLUSTER BY: order_number, product_code | Rationale: Clustering on order_number, product_code co-locates rows that are joined and filtered together.
