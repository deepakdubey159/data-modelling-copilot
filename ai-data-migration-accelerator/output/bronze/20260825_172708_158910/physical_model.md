# Executive Summary

21 tables and 76 columns, carrying 50 constraints and 43 recommended indexes. 10 tables are transactional, 5 hold master data and 6 are lookups; 0 are candidates for partitioning. Types, lengths and precision are generic — no vendor syntax appears until DDL generation.

> Derived deterministically from `logical_model.json`. Business descriptions are not repeated here — each table names the logical entity it came from. Types, lengths and precision are generic: no vendor syntax appears until DDL generation.

# Physical Architecture Overview

- **Database:** datamodel
- **Tables:** 21 (6 lookup, 5 master, 10 transaction)
- **Columns:** 76
- **Constraints:** 50
- **Recommended indexes:** 43
- **Naming:** snake_case, max 30 characters

**Naming notes**

- 18 foreign key columns were retyped to match the key they reference. A foreign key must be physically comparable to its parent column or the constraint cannot be created.

**Design notes**

- Data types are generic storage classes. STRING(255) states the shape of the data, not a vendor type; mapping onto VARCHAR2, NVARCHAR or STRING happens during DDL generation.
- Every foreign key carries an index recommendation. Unindexed foreign keys are a routine cause of slow joins and of lock escalation on parent deletes.
- Check constraints are only added where the domain makes the rule certain. Amounts are deliberately left unconstrained because refunds, credits and adjustments are legitimately negative.

# Physical Tables

| Table | Classification | Size | Growth | Columns | Logical entity |
|---|---|---|---|---|---|
| `audit_log` | Lookup | Small | Static | 5 | Audit Log |
| `category` | Lookup | Small | Static | 1 | Category |
| `city` | Transaction | Very Large | High | 2 | City |
| `country` | Lookup | Small | Static | 3 | Country |
| `customer` | Master | Medium | Low | 8 | Customer |
| `department` | Lookup | Small | Static | 1 | Department |
| `employee` | Master | Medium | Low | 7 | Employee |
| `inventory` | Transaction | Very Large | High | 4 | Inventory |
| `order` | Master | Medium | Low | 5 | Order |
| `order_item` | Transaction | Very Large | High | 5 | Order Item |
| `payment` | Transaction | Large | Moderate | 5 | Payment |
| `product` | Master | Medium | Low | 6 | Product |
| `product_promotion` | Transaction | Very Large | High | 2 | Product Promotion |
| `product_promotion_association` | Transaction | Very Large | High | 2 | Product Promotion Association |
| `product_warehouse_association` | Transaction | Very Large | High | 2 | Product Warehouse Association |
| `promotion` | Lookup | Small | Static | 2 | Promotion |
| `return` | Transaction | Large | Moderate | 4 | Return |
| `shipment` | Transaction | Large | Moderate | 4 | Shipment |
| `state` | Transaction | Very Large | High | 2 | State |
| `supplier` | Lookup | Small | Static | 4 | Supplier |
| `warehouse` | Master | Medium | Low | 2 | Warehouse |

# Column Definitions

## `audit_log`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `audit_id` | STRING(255) | NOT NULL | PK |  |
| `table_name` | STRING(100) | NULL |  |  |
| `operation` | STRING(30) | NULL |  |  |
| `user_name` | STRING(100) | NULL |  |  |
| `operation_timestamp` | STRING(255) | NULL |  |  |

## `category`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `category_name` | STRING(100) | NOT NULL | PK |  |

## `city`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `city_name` | STRING(100) | NOT NULL | PK |  |
| `state_name` | STRING(100) | NOT NULL | PK FK |  |

## `country`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `country_code` | STRING(255) | NOT NULL | PK |  |
| `country_name` | STRING(100) | NULL |  |  |
| `created_at` | STRING(255) | NULL |  |  |

## `customer`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `customer_number` | STRING(255) | NOT NULL | PK |  |
| `first_name` | STRING(100) | NULL |  |  |
| `last_name` | STRING(100) | NULL |  |  |
| `email` | STRING(255) | NULL | AK |  |
| `phone` | STRING(30) | NULL |  |  |
| `credit_limit` | STRING(255) | NULL |  |  |
| `status` | STRING(30) | NULL |  |  |
| `city_name` | STRING(100) | NULL | FK |  |

## `department`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `department_name` | STRING(100) | NOT NULL | PK |  |

## `employee`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `email` | STRING(255) | NOT NULL | PK |  |
| `first_name` | STRING(100) | NULL |  |  |
| `last_name` | STRING(100) | NULL |  |  |
| `salary` | DECIMAL(18,2) | NULL |  |  |
| `hire_date` | STRING(255) | NULL |  |  |
| `department_name` | STRING(100) | NULL | FK |  |
| `parent_email` | STRING(255) | NULL | FK |  |

## `inventory`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `warehouse_name` | STRING(100) | NOT NULL | PK FK |  |
| `sku` | STRING(30) | NOT NULL | PK FK |  |
| `quantity` | INTEGER | NULL |  |  |
| `reorder_level` | STRING(255) | NULL |  |  |

## `order`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `order_id` | STRING(255) | NOT NULL | PK |  |
| `order_date` | STRING(255) | NULL |  |  |
| `order_status` | STRING(255) | NULL |  |  |
| `employee_email` | STRING(255) | NULL | FK |  |
| `customer_number` | STRING(255) | NULL | FK |  |

## `order_item`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `order_id` | STRING(255) | NOT NULL | PK FK |  |
| `line_number` | STRING(255) | NOT NULL | PK |  |
| `quantity` | INTEGER | NULL |  |  |
| `unit_price` | STRING(255) | NULL |  |  |
| `product_sku` | STRING(30) | NULL | FK |  |

## `payment`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `payment_id` | STRING(255) | NOT NULL | PK |  |
| `payment_method` | STRING(255) | NULL |  |  |
| `payment_date` | STRING(255) | NULL |  |  |
| `amount` | DECIMAL(18,2) | NULL |  |  |
| `order_id` | STRING(255) | NULL | FK |  |

## `product`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `sku` | STRING(30) | NOT NULL | PK |  |
| `product_name` | STRING(100) | NULL |  |  |
| `unit_price` | STRING(255) | NULL |  |  |
| `status` | STRING(30) | NULL |  |  |
| `category_name` | STRING(100) | NULL | FK |  |
| `supplier_name` | STRING(100) | NULL | FK |  |

## `product_promotion`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `sku` | STRING(30) | NOT NULL | PK FK |  |
| `promotion_name` | STRING(100) | NOT NULL | PK FK |  |

## `product_promotion_association`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `product_sku` | STRING(30) | NOT NULL | PK FK |  |
| `promotion_name` | STRING(100) | NOT NULL | PK FK |  |

## `product_warehouse_association`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `product_sku` | STRING(30) | NOT NULL | PK FK |  |
| `warehouse_name` | STRING(100) | NOT NULL | PK FK |  |

## `promotion`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `promotion_name` | STRING(100) | NOT NULL | PK |  |
| `discount_percent` | STRING(255) | NULL |  |  |

## `return`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `return_id` | STRING(255) | NOT NULL | PK |  |
| `return_reason` | STRING(500) | NULL |  |  |
| `product_sku` | STRING(30) | NULL | FK |  |
| `order_id` | STRING(255) | NULL | FK |  |

## `shipment`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `tracking_number` | STRING(255) | NOT NULL | PK |  |
| `shipped_date` | STRING(255) | NULL |  |  |
| `warehouse_name` | STRING(100) | NULL | FK |  |
| `order_id` | STRING(255) | NULL | FK |  |

## `state`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `state_name` | STRING(100) | NOT NULL | PK |  |
| `country_code` | STRING(255) | NOT NULL | PK FK |  |

## `supplier`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `supplier_name` | STRING(100) | NOT NULL | PK |  |
| `contact_name` | STRING(100) | NULL |  |  |
| `email` | STRING(255) | NULL | AK |  |
| `phone` | STRING(30) | NULL |  |  |

## `warehouse`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `warehouse_name` | STRING(100) | NOT NULL | PK |  |
| `city_name` | STRING(100) | NULL | FK |  |

# Constraints

| Constraint | Type | Table | Columns | References |
|---|---|---|---|---|
| `pk_audit_log` | Primary Key | `audit_log` | audit_id |  |
| `pk_category` | Primary Key | `category` | category_name |  |
| `pk_city` | Primary Key | `city` | city_name, state_name |  |
| `fk_city_state_name` | Foreign Key | `city` | state_name | `state`(state_name) |
| `pk_country` | Primary Key | `country` | country_code |  |
| `pk_customer` | Primary Key | `customer` | customer_number |  |
| `uq_customer_email` | Unique | `customer` | email |  |
| `fk_customer_city_name` | Foreign Key | `customer` | city_name | `city`(city_name) |
| `pk_department` | Primary Key | `department` | department_name |  |
| `pk_employee` | Primary Key | `employee` | email |  |
| `fk_employee_department_name` | Foreign Key | `employee` | department_name | `department`(department_name) |
| `fk_employee_parent_email` | Foreign Key | `employee` | parent_email | `employee`(email) |
| `pk_inventory` | Primary Key | `inventory` | warehouse_name, sku |  |
| `fk_inventory_warehouse_name` | Foreign Key | `inventory` | warehouse_name | `warehouse`(warehouse_name) |
| `fk_inventory_sku` | Foreign Key | `inventory` | sku | `product`(sku) |
| `ck_inventory_quantity` | Check | `inventory` | quantity | `quantity >= 0` |
| `pk_order` | Primary Key | `order` | order_id |  |
| `fk_order_employee_email` | Foreign Key | `order` | employee_email | `employee`(email) |
| `fk_order_customer_number` | Foreign Key | `order` | customer_number | `customer`(customer_number) |
| `pk_order_item` | Primary Key | `order_item` | order_id, line_number |  |
| `fk_order_item_order_id` | Foreign Key | `order_item` | order_id | `order`(order_id) |
| `fk_order_item_product_sku` | Foreign Key | `order_item` | product_sku | `product`(sku) |
| `ck_order_item_quantity` | Check | `order_item` | quantity | `quantity >= 0` |
| `pk_payment` | Primary Key | `payment` | payment_id |  |
| `fk_payment_order_id` | Foreign Key | `payment` | order_id | `order`(order_id) |
| `pk_product` | Primary Key | `product` | sku |  |
| `fk_product_category_name` | Foreign Key | `product` | category_name | `category`(category_name) |
| `fk_product_supplier_name` | Foreign Key | `product` | supplier_name | `supplier`(supplier_name) |
| `pk_product_promotion` | Primary Key | `product_promotion` | sku, promotion_name |  |
| `fk_product_promotion_sku` | Foreign Key | `product_promotion` | sku | `product`(sku) |
| `fk_product_promotion_promotion` | Foreign Key | `product_promotion` | promotion_name | `promotion`(promotion_name) |
| `pk_product_promotion` | Primary Key | `product_promotion_association` | product_sku, promotion_name |  |
| `fk_product_promotion` | Foreign Key | `product_promotion_association` | product_sku | `product`(sku) |
| `fk_product_promotion` | Foreign Key | `product_promotion_association` | promotion_name | `promotion`(promotion_name) |
| `pk_product_warehouse` | Primary Key | `product_warehouse_association` | product_sku, warehouse_name |  |
| `fk_product_warehouse` | Foreign Key | `product_warehouse_association` | product_sku | `product`(sku) |
| `fk_product_warehouse` | Foreign Key | `product_warehouse_association` | warehouse_name | `warehouse`(warehouse_name) |
| `pk_promotion` | Primary Key | `promotion` | promotion_name |  |
| `pk_return` | Primary Key | `return` | return_id |  |
| `fk_return_product_sku` | Foreign Key | `return` | product_sku | `product`(sku) |
| `fk_return_order_id` | Foreign Key | `return` | order_id | `order`(order_id) |
| `pk_shipment` | Primary Key | `shipment` | tracking_number |  |
| `fk_shipment_warehouse_name` | Foreign Key | `shipment` | warehouse_name | `warehouse`(warehouse_name) |
| `fk_shipment_order_id` | Foreign Key | `shipment` | order_id | `order`(order_id) |
| `pk_state` | Primary Key | `state` | state_name, country_code |  |
| `fk_state_country_code` | Foreign Key | `state` | country_code | `country`(country_code) |
| `pk_supplier` | Primary Key | `supplier` | supplier_name |  |
| `uq_supplier_email` | Unique | `supplier` | email |  |
| `pk_warehouse` | Primary Key | `warehouse` | warehouse_name |  |
| `fk_warehouse_city_name` | Foreign Key | `warehouse` | city_name | `city`(city_name) |

# Index Recommendations

| Index | Table | Columns | Unique | Purpose |
|---|---|---|---|---|
| `idx_audit_log_pk` | `audit_log` | audit_id | Yes | Primary Key |
| `idx_category_pk` | `category` | category_name | Yes | Primary Key |
| `idx_city_pk` | `city` | city_name, state_name | Yes | Primary Key |
| `idx_city_state_name` | `city` | state_name | No | Foreign Key |
| `idx_country_pk` | `country` | country_code | Yes | Primary Key |
| `idx_customer_pk` | `customer` | customer_number | Yes | Primary Key |
| `idx_customer_email` | `customer` | email | Yes | Unique Constraint |
| `idx_customer_city_name` | `customer` | city_name | No | Foreign Key |
| `idx_department_pk` | `department` | department_name | Yes | Primary Key |
| `idx_employee_pk` | `employee` | email | Yes | Primary Key |
| `idx_employee_department_name` | `employee` | department_name | No | Foreign Key |
| `idx_employee_parent_email` | `employee` | parent_email | No | Foreign Key |
| `idx_inventory_pk` | `inventory` | warehouse_name, sku | Yes | Primary Key |
| `idx_inventory_sku` | `inventory` | sku | No | Foreign Key |
| `idx_order_pk` | `order` | order_id | Yes | Primary Key |
| `idx_order_employee_email` | `order` | employee_email | No | Foreign Key |
| `idx_order_customer_number` | `order` | customer_number | No | Foreign Key |
| `idx_order_item_pk` | `order_item` | order_id, line_number | Yes | Primary Key |
| `idx_order_item_product_sku` | `order_item` | product_sku | No | Foreign Key |
| `idx_payment_pk` | `payment` | payment_id | Yes | Primary Key |
| `idx_payment_order_id` | `payment` | order_id | No | Foreign Key |
| `idx_product_pk` | `product` | sku | Yes | Primary Key |
| `idx_product_category_name` | `product` | category_name | No | Foreign Key |
| `idx_product_supplier_name` | `product` | supplier_name | No | Foreign Key |
| `idx_product_promotion_pk` | `product_promotion` | sku, promotion_name | Yes | Primary Key |
| `idx_product_promotion` | `product_promotion` | promotion_name | No | Foreign Key |
| `idx_product_promotion` | `product_promotion_association` | product_sku, promotion_name | Yes | Primary Key |
| `idx_product_promotion` | `product_promotion_association` | promotion_name | No | Foreign Key |
| `idx_product_warehouse` | `product_warehouse_association` | product_sku, warehouse_name | Yes | Primary Key |
| `idx_product_warehouse` | `product_warehouse_association` | warehouse_name | No | Foreign Key |
| `idx_promotion_pk` | `promotion` | promotion_name | Yes | Primary Key |
| `idx_return_pk` | `return` | return_id | Yes | Primary Key |
| `idx_return_product_sku` | `return` | product_sku | No | Foreign Key |
| `idx_return_order_id` | `return` | order_id | No | Foreign Key |
| `idx_shipment_pk` | `shipment` | tracking_number | Yes | Primary Key |
| `idx_shipment_warehouse_name` | `shipment` | warehouse_name | No | Foreign Key |
| `idx_shipment_order_id` | `shipment` | order_id | No | Foreign Key |
| `idx_state_pk` | `state` | state_name, country_code | Yes | Primary Key |
| `idx_state_country_code` | `state` | country_code | No | Foreign Key |
| `idx_supplier_pk` | `supplier` | supplier_name | Yes | Primary Key |
| `idx_supplier_email` | `supplier` | email | Yes | Unique Constraint |
| `idx_warehouse_pk` | `warehouse` | warehouse_name | Yes | Primary Key |
| `idx_warehouse_city_name` | `warehouse` | city_name | No | Foreign Key |

# Storage Recommendations

### `audit_log`

- **Partition candidates:** None
- **Clustering candidates:** None
- Lookup data is small enough to be scanned or cached in full; partitioning would add maintenance without reducing work.

### `category`

- **Partition candidates:** None
- **Clustering candidates:** None
- Lookup data is small enough to be scanned or cached in full; partitioning would add maintenance without reducing work.

### `city`

- **Partition candidates:** None
- **Clustering candidates:** state_name
- Clustering on state_name co-locates rows that are joined and filtered together.

### `country`

- **Partition candidates:** None
- **Clustering candidates:** None
- Lookup data is small enough to be scanned or cached in full; partitioning would add maintenance without reducing work.

### `customer`

- **Partition candidates:** None
- **Clustering candidates:** customer_number
- Master data is looked up by key; clustering on it keeps those reads to a minimum of blocks.

### `department`

- **Partition candidates:** None
- **Clustering candidates:** None
- Lookup data is small enough to be scanned or cached in full; partitioning would add maintenance without reducing work.

### `employee`

- **Partition candidates:** None
- **Clustering candidates:** email
- Master data is looked up by key; clustering on it keeps those reads to a minimum of blocks.

### `inventory`

- **Partition candidates:** None
- **Clustering candidates:** warehouse_name, sku
- Clustering on warehouse_name, sku co-locates rows that are joined and filtered together.

### `order`

- **Partition candidates:** None
- **Clustering candidates:** order_id
- Master data is looked up by key; clustering on it keeps those reads to a minimum of blocks.

### `order_item`

- **Partition candidates:** None
- **Clustering candidates:** order_id, product_sku
- Clustering on order_id, product_sku co-locates rows that are joined and filtered together.

### `payment`

- **Partition candidates:** None
- **Clustering candidates:** order_id
- Clustering on order_id co-locates rows that are joined and filtered together.

### `product`

- **Partition candidates:** None
- **Clustering candidates:** sku
- Master data is looked up by key; clustering on it keeps those reads to a minimum of blocks.

### `product_promotion`

- **Partition candidates:** None
- **Clustering candidates:** sku, promotion_name
- Clustering on sku, promotion_name co-locates rows that are joined and filtered together.

### `product_promotion_association`

- **Partition candidates:** None
- **Clustering candidates:** product_sku, promotion_name
- Clustering on product_sku, promotion_name co-locates rows that are joined and filtered together.

### `product_warehouse_association`

- **Partition candidates:** None
- **Clustering candidates:** product_sku, warehouse_name
- Clustering on product_sku, warehouse_name co-locates rows that are joined and filtered together.

### `promotion`

- **Partition candidates:** None
- **Clustering candidates:** None
- Lookup data is small enough to be scanned or cached in full; partitioning would add maintenance without reducing work.

### `return`

- **Partition candidates:** None
- **Clustering candidates:** product_sku, order_id
- Clustering on product_sku, order_id co-locates rows that are joined and filtered together.

### `shipment`

- **Partition candidates:** None
- **Clustering candidates:** warehouse_name, order_id
- Clustering on warehouse_name, order_id co-locates rows that are joined and filtered together.

### `state`

- **Partition candidates:** None
- **Clustering candidates:** country_code
- Clustering on country_code co-locates rows that are joined and filtered together.

### `supplier`

- **Partition candidates:** None
- **Clustering candidates:** None
- Lookup data is small enough to be scanned or cached in full; partitioning would add maintenance without reducing work.

### `warehouse`

- **Partition candidates:** None
- **Clustering candidates:** warehouse_name
- Master data is looked up by key; clustering on it keeps those reads to a minimum of blocks.
