# Executive Summary

18 tables and 57 columns, carrying 22 constraints and 20 recommended indexes. 0 tables are transactional, 0 hold master data and 18 are lookups; 0 are candidates for partitioning. Types, lengths and precision are generic — no vendor syntax appears until DDL generation.

> Derived deterministically from `logical_model.json`. Business descriptions are not repeated here — each table names the logical entity it came from. Types, lengths and precision are generic: no vendor syntax appears until DDL generation.

# Physical Architecture Overview

- **Database:** datamodel
- **Tables:** 18 (18 lookup, 0 master, 0 transaction)
- **Columns:** 57
- **Constraints:** 22
- **Recommended indexes:** 20
- **Naming:** snake_case, max 30 characters

**Design notes**

- Data types are generic storage classes. STRING(255) states the shape of the data, not a vendor type; mapping onto VARCHAR2, NVARCHAR or STRING happens during DDL generation.
- Every foreign key carries an index recommendation. Unindexed foreign keys are a routine cause of slow joins and of lock escalation on parent deletes.
- Check constraints are only added where the domain makes the rule certain. Amounts are deliberately left unconstrained because refunds, credits and adjustments are legitimately negative.

# Physical Tables

| Table | Classification | Size | Growth | Columns | Logical entity |
|---|---|---|---|---|---|
| `audit_log` | Lookup | Small | Static | 5 | Audit Log |
| `category` | Lookup | Small | Static | 1 | Category |
| `city` | Lookup | Small | Static | 2 | City |
| `country` | Lookup | Small | Static | 3 | Country |
| `customer` | Lookup | Small | Static | 7 | Customer |
| `department` | Lookup | Small | Static | 1 | Department |
| `employee` | Lookup | Small | Static | 5 | Employee |
| `inventory` | Lookup | Small | Static | 4 | Inventory |
| `order` | Lookup | Small | Static | 3 | Order |
| `order_line` | Lookup | Small | Static | 4 | Order Line |
| `payment` | Lookup | Small | Static | 4 | Payment |
| `product` | Lookup | Small | Static | 4 | Product |
| `promotion` | Lookup | Small | Static | 2 | Promotion |
| `return` | Lookup | Small | Static | 2 | Return |
| `shipment` | Lookup | Small | Static | 2 | Shipment |
| `state` | Lookup | Small | Static | 2 | State |
| `supplier` | Lookup | Small | Static | 4 | Supplier |
| `warehouse` | Lookup | Small | Static | 2 | Warehouse |

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
| `state_name` | STRING(100) | NOT NULL | PK |  |

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

## `inventory`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `warehouse_name` | STRING(100) | NOT NULL | PK |  |
| `sku` | STRING(30) | NOT NULL | PK |  |
| `quantity` | INTEGER | NULL |  |  |
| `reorder_level` | STRING(255) | NULL |  |  |

## `order`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `order_id` | STRING(255) | NOT NULL | PK |  |
| `order_date` | STRING(255) | NULL |  |  |
| `order_status` | STRING(255) | NULL |  |  |

## `order_line`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `order_id` | STRING(255) | NOT NULL | PK |  |
| `line_number` | STRING(255) | NOT NULL | PK |  |
| `quantity` | INTEGER | NULL |  |  |
| `unit_price` | STRING(255) | NULL |  |  |

## `payment`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `payment_id` | STRING(255) | NOT NULL | PK |  |
| `payment_method` | STRING(255) | NULL |  |  |
| `payment_date` | STRING(255) | NULL |  |  |
| `amount` | DECIMAL(18,2) | NULL |  |  |

## `product`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `sku` | STRING(30) | NOT NULL | PK |  |
| `product_name` | STRING(100) | NULL |  |  |
| `unit_price` | STRING(255) | NULL |  |  |
| `status` | STRING(30) | NULL |  |  |

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

## `shipment`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `tracking_number` | STRING(255) | NOT NULL | PK |  |
| `shipped_date` | STRING(255) | NULL |  |  |

## `state`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `state_name` | STRING(100) | NOT NULL | PK |  |
| `country_code` | STRING(255) | NOT NULL | PK |  |

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
| `city_name` | STRING(100) | NOT NULL | PK |  |

# Constraints

| Constraint | Type | Table | Columns | References |
|---|---|---|---|---|
| `pk_audit_log` | Primary Key | `audit_log` | audit_id |  |
| `pk_category` | Primary Key | `category` | category_name |  |
| `pk_city` | Primary Key | `city` | city_name, state_name |  |
| `pk_country` | Primary Key | `country` | country_code |  |
| `pk_customer` | Primary Key | `customer` | customer_number |  |
| `uq_customer_email` | Unique | `customer` | email |  |
| `pk_department` | Primary Key | `department` | department_name |  |
| `pk_employee` | Primary Key | `employee` | email |  |
| `pk_inventory` | Primary Key | `inventory` | warehouse_name, sku |  |
| `ck_inventory_quantity` | Check | `inventory` | quantity | `quantity >= 0` |
| `pk_order` | Primary Key | `order` | order_id |  |
| `pk_order_line` | Primary Key | `order_line` | order_id, line_number |  |
| `ck_order_line_quantity` | Check | `order_line` | quantity | `quantity >= 0` |
| `pk_payment` | Primary Key | `payment` | payment_id |  |
| `pk_product` | Primary Key | `product` | sku |  |
| `pk_promotion` | Primary Key | `promotion` | promotion_name |  |
| `pk_return` | Primary Key | `return` | return_id |  |
| `pk_shipment` | Primary Key | `shipment` | tracking_number |  |
| `pk_state` | Primary Key | `state` | state_name, country_code |  |
| `pk_supplier` | Primary Key | `supplier` | supplier_name |  |
| `uq_supplier_email` | Unique | `supplier` | email |  |
| `pk_warehouse` | Primary Key | `warehouse` | warehouse_name, city_name |  |

# Index Recommendations

| Index | Table | Columns | Unique | Purpose |
|---|---|---|---|---|
| `idx_audit_log_pk` | `audit_log` | audit_id | Yes | Primary Key |
| `idx_category_pk` | `category` | category_name | Yes | Primary Key |
| `idx_city_pk` | `city` | city_name, state_name | Yes | Primary Key |
| `idx_country_pk` | `country` | country_code | Yes | Primary Key |
| `idx_customer_pk` | `customer` | customer_number | Yes | Primary Key |
| `idx_customer_email` | `customer` | email | Yes | Unique Constraint |
| `idx_department_pk` | `department` | department_name | Yes | Primary Key |
| `idx_employee_pk` | `employee` | email | Yes | Primary Key |
| `idx_inventory_pk` | `inventory` | warehouse_name, sku | Yes | Primary Key |
| `idx_order_pk` | `order` | order_id | Yes | Primary Key |
| `idx_order_line_pk` | `order_line` | order_id, line_number | Yes | Primary Key |
| `idx_payment_pk` | `payment` | payment_id | Yes | Primary Key |
| `idx_product_pk` | `product` | sku | Yes | Primary Key |
| `idx_promotion_pk` | `promotion` | promotion_name | Yes | Primary Key |
| `idx_return_pk` | `return` | return_id | Yes | Primary Key |
| `idx_shipment_pk` | `shipment` | tracking_number | Yes | Primary Key |
| `idx_state_pk` | `state` | state_name, country_code | Yes | Primary Key |
| `idx_supplier_pk` | `supplier` | supplier_name | Yes | Primary Key |
| `idx_supplier_email` | `supplier` | email | Yes | Unique Constraint |
| `idx_warehouse_pk` | `warehouse` | warehouse_name, city_name | Yes | Primary Key |

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
- **Clustering candidates:** None
- Lookup data is small enough to be scanned or cached in full; partitioning would add maintenance without reducing work.

### `country`

- **Partition candidates:** None
- **Clustering candidates:** None
- Lookup data is small enough to be scanned or cached in full; partitioning would add maintenance without reducing work.

### `customer`

- **Partition candidates:** None
- **Clustering candidates:** None
- Lookup data is small enough to be scanned or cached in full; partitioning would add maintenance without reducing work.

### `department`

- **Partition candidates:** None
- **Clustering candidates:** None
- Lookup data is small enough to be scanned or cached in full; partitioning would add maintenance without reducing work.

### `employee`

- **Partition candidates:** None
- **Clustering candidates:** None
- Lookup data is small enough to be scanned or cached in full; partitioning would add maintenance without reducing work.

### `inventory`

- **Partition candidates:** None
- **Clustering candidates:** None
- Lookup data is small enough to be scanned or cached in full; partitioning would add maintenance without reducing work.

### `order`

- **Partition candidates:** None
- **Clustering candidates:** None
- Lookup data is small enough to be scanned or cached in full; partitioning would add maintenance without reducing work.

### `order_line`

- **Partition candidates:** None
- **Clustering candidates:** None
- Lookup data is small enough to be scanned or cached in full; partitioning would add maintenance without reducing work.

### `payment`

- **Partition candidates:** None
- **Clustering candidates:** None
- Lookup data is small enough to be scanned or cached in full; partitioning would add maintenance without reducing work.

### `product`

- **Partition candidates:** None
- **Clustering candidates:** None
- Lookup data is small enough to be scanned or cached in full; partitioning would add maintenance without reducing work.

### `promotion`

- **Partition candidates:** None
- **Clustering candidates:** None
- Lookup data is small enough to be scanned or cached in full; partitioning would add maintenance without reducing work.

### `return`

- **Partition candidates:** None
- **Clustering candidates:** None
- Lookup data is small enough to be scanned or cached in full; partitioning would add maintenance without reducing work.

### `shipment`

- **Partition candidates:** None
- **Clustering candidates:** None
- Lookup data is small enough to be scanned or cached in full; partitioning would add maintenance without reducing work.

### `state`

- **Partition candidates:** None
- **Clustering candidates:** None
- Lookup data is small enough to be scanned or cached in full; partitioning would add maintenance without reducing work.

### `supplier`

- **Partition candidates:** None
- **Clustering candidates:** None
- Lookup data is small enough to be scanned or cached in full; partitioning would add maintenance without reducing work.

### `warehouse`

- **Partition candidates:** None
- **Clustering candidates:** None
- Lookup data is small enough to be scanned or cached in full; partitioning would add maintenance without reducing work.
