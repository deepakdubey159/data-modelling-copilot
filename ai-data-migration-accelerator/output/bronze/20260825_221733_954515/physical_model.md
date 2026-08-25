# Executive Summary

7 tables and 54 columns, carrying 19 constraints and 15 recommended indexes. 3 tables are transactional, 1 hold master data and 3 are lookups; 0 are candidates for partitioning. Types, lengths and precision are generic — no vendor syntax appears until DDL generation.

> Derived deterministically from `logical_model.json`. Business descriptions are not repeated here — each table names the logical entity it came from. Types, lengths and precision are generic: no vendor syntax appears until DDL generation.

# Physical Architecture Overview

- **Database:** datamodel
- **Tables:** 7 (3 lookup, 1 master, 3 transaction)
- **Columns:** 54
- **Constraints:** 19
- **Recommended indexes:** 15
- **Naming:** snake_case, max 30 characters

**Naming notes**

- 6 foreign key columns were retyped to match the key they reference. A foreign key must be physically comparable to its parent column or the constraint cannot be created.

**Design notes**

- Data types are generic storage classes. STRING(255) states the shape of the data, not a vendor type; mapping onto VARCHAR2, NVARCHAR or STRING happens during DDL generation.
- Every foreign key carries an index recommendation. Unindexed foreign keys are a routine cause of slow joins and of lock escalation on parent deletes.
- Check constraints are only added where the domain makes the rule certain. Amounts are deliberately left unconstrained because refunds, credits and adjustments are legitimately negative.

# Physical Tables

| Table | Classification | Size | Growth | Columns | Logical entity |
|---|---|---|---|---|---|
| `customer` | Lookup | Small | Static | 14 | Customer |
| `order` | Master | Medium | Low | 13 | Order |
| `order_item` | Transaction | Large | Moderate | 6 | Order Item |
| `order_line_item` | Lookup | Small | Static | 5 | Order Line Item |
| `order_product` | Transaction | Large | Moderate | 6 | Order Product |
| `order_product_association` | Transaction | Very Large | High | 2 | Order Product Association |
| `product` | Lookup | Small | Static | 8 | Product |

# Column Definitions

## `customer`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `customer_code` | STRING(20) | NOT NULL | PK |  |
| `first_name` | STRING(100) | NOT NULL |  |  |
| `last_name` | STRING(100) | NULL |  |  |
| `email` | STRING(255) | NULL | AK |  |
| `phone_number` | STRING(20) | NULL | AK |  |
| `date_of_birth` | DATE | NULL |  |  |
| `gender` | STRING(10) | NULL |  |  |
| `city` | STRING(100) | NULL |  |  |
| `state` | STRING(100) | NULL |  |  |
| `country` | STRING(100) | NULL |  |  |
| `postal_code` | STRING(20) | NULL | AK |  |
| `customer_status` | STRING(20) | NULL |  |  |
| `credit_limit` | DECIMAL(12,2) | NULL |  |  |
| `is_active` | BOOLEAN | NULL |  |  |

## `order`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `order_number` | STRING(30) | NOT NULL | PK |  |
| `order_date` | TIMESTAMP | NULL |  |  |
| `order_status` | STRING(20) | NULL |  |  |
| `payment_method` | STRING(30) | NULL |  |  |
| `total_amount` | DECIMAL(12,2) | NULL |  |  |
| `tax_amount` | DECIMAL(12,2) | NULL |  |  |
| `discount_amount` | DECIMAL(12,2) | NULL |  |  |
| `shipping_amount` | DECIMAL(12,2) | NULL |  |  |
| `shipped_date` | TIMESTAMP | NULL |  |  |
| `remarks` | STRING | NULL |  |  |
| `created_by` | STRING(50) | NULL |  |  |
| `created_date` | TIMESTAMP | NULL |  |  |
| `customer_code` | STRING(20) | NOT NULL | FK |  |

## `order_item`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `order_item_id` | INTEGER | NOT NULL | PK |  |
| `product_name` | STRING(200) | NULL |  |  |
| `quantity` | INTEGER | NOT NULL |  |  |
| `unit_price` | DECIMAL(10,2) | NULL |  |  |
| `total_price` | DECIMAL(12,2) | NULL |  |  |
| `order_number` | STRING(30) | NOT NULL | FK |  |

## `order_line_item`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `order_id` | INTEGER | NOT NULL | PK |  |
| `product_name` | STRING(200) | NOT NULL | PK |  |
| `quantity` | INTEGER | NOT NULL |  |  |
| `unit_price` | DECIMAL(10,2) | NULL |  |  |
| `total_price` | DECIMAL(12,2) | NULL |  |  |

## `order_product`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `order_id` | INTEGER | NOT NULL | PK |  |
| `product_id` | INTEGER | NOT NULL | PK |  |
| `quantity` | INTEGER | NULL |  |  |
| `selling_price` | DECIMAL(10,2) | NULL |  |  |
| `product_code` | STRING(20) | NOT NULL | FK |  |
| `order_number` | STRING(30) | NOT NULL | FK |  |

## `order_product_association`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `order_number` | STRING(30) | NOT NULL | PK FK |  |
| `product_code` | STRING(20) | NOT NULL | PK FK |  |

## `product`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| `product_code` | STRING(20) | NOT NULL | PK |  |
| `product_name` | STRING(200) | NULL |  |  |
| `category` | STRING(100) | NULL |  |  |
| `price` | DECIMAL(10,2) | NULL |  |  |
| `stock_quantity` | INTEGER | NULL |  |  |
| `supplier_name` | STRING(100) | NULL |  |  |
| `is_active` | BOOLEAN | NULL |  |  |
| `created_date` | TIMESTAMP | NULL |  |  |

# Constraints

| Constraint | Type | Table | Columns | References |
|---|---|---|---|---|
| `pk_customer` | Primary Key | `customer` | customer_code |  |
| `uq_customer_email` | Unique | `customer` | email |  |
| `uq_customer_phone_number` | Unique | `customer` | phone_number |  |
| `uq_customer_postal_code` | Unique | `customer` | postal_code |  |
| `pk_order` | Primary Key | `order` | order_number |  |
| `fk_order_customer_code` | Foreign Key | `order` | customer_code | `customer`(customer_code) |
| `pk_order_item` | Primary Key | `order_item` | order_item_id |  |
| `fk_order_item_order_number` | Foreign Key | `order_item` | order_number | `order`(order_number) |
| `ck_order_item_quantity` | Check | `order_item` | quantity | `quantity >= 0` |
| `pk_order_line_item` | Primary Key | `order_line_item` | order_id, product_name |  |
| `ck_order_line_item_quantity` | Check | `order_line_item` | quantity | `quantity >= 0` |
| `pk_order_product` | Primary Key | `order_product` | order_id, product_id |  |
| `fk_order_product_product_code` | Foreign Key | `order_product` | product_code | `product`(product_code) |
| `fk_order_product_order_number` | Foreign Key | `order_product` | order_number | `order`(order_number) |
| `ck_order_product_quantity` | Check | `order_product` | quantity | `quantity >= 0` |
| `pk_order_product_association` | Primary Key | `order_product_association` | order_number, product_code |  |
| `fk_order_product_association` | Foreign Key | `order_product_association` | order_number | `order`(order_number) |
| `fk_order_product_association` | Foreign Key | `order_product_association` | product_code | `product`(product_code) |
| `pk_product` | Primary Key | `product` | product_code |  |

# Index Recommendations

| Index | Table | Columns | Unique | Purpose |
|---|---|---|---|---|
| `idx_customer_pk` | `customer` | customer_code | Yes | Primary Key |
| `idx_customer_email` | `customer` | email | Yes | Unique Constraint |
| `idx_customer_phone_number` | `customer` | phone_number | Yes | Unique Constraint |
| `idx_customer_postal_code` | `customer` | postal_code | Yes | Unique Constraint |
| `idx_order_pk` | `order` | order_number | Yes | Primary Key |
| `idx_order_customer_code` | `order` | customer_code | No | Foreign Key |
| `idx_order_item_pk` | `order_item` | order_item_id | Yes | Primary Key |
| `idx_order_item_order_number` | `order_item` | order_number | No | Foreign Key |
| `idx_order_line_item_pk` | `order_line_item` | order_id, product_name | Yes | Primary Key |
| `idx_order_product_pk` | `order_product` | order_id, product_id | Yes | Primary Key |
| `idx_order_product_product_code` | `order_product` | product_code | No | Foreign Key |
| `idx_order_product_order_number` | `order_product` | order_number | No | Foreign Key |
| `idx_order_product_association` | `order_product_association` | order_number, product_code | Yes | Primary Key |
| `idx_order_product_association` | `order_product_association` | product_code | No | Foreign Key |
| `idx_product_pk` | `product` | product_code | Yes | Primary Key |

# Storage Recommendations

### `customer`

- **Partition candidates:** None
- **Clustering candidates:** None
- Lookup data is small enough to be scanned or cached in full; partitioning would add maintenance without reducing work.

### `order`

- **Partition candidates:** None
- **Clustering candidates:** order_number
- Master data is looked up by key; clustering on it keeps those reads to a minimum of blocks.

### `order_item`

- **Partition candidates:** None
- **Clustering candidates:** order_number
- Clustering on order_number co-locates rows that are joined and filtered together.

### `order_line_item`

- **Partition candidates:** None
- **Clustering candidates:** None
- Lookup data is small enough to be scanned or cached in full; partitioning would add maintenance without reducing work.

### `order_product`

- **Partition candidates:** None
- **Clustering candidates:** product_code, order_number
- Clustering on product_code, order_number co-locates rows that are joined and filtered together.

### `order_product_association`

- **Partition candidates:** None
- **Clustering candidates:** order_number, product_code
- Clustering on order_number, product_code co-locates rows that are joined and filtered together.

### `product`

- **Partition candidates:** None
- **Clustering candidates:** None
- Lookup data is small enough to be scanned or cached in full; partitioning would add maintenance without reducing work.
