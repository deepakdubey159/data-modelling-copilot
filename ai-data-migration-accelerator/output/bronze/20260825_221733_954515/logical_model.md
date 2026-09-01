# Executive Summary

Logical design for datamodel, derived from the conceptual model. 7 entities carry 6 relationships: 1 associative entities resolve many-to-many relationships and 0 entities are identified through a parent. 0 entities required a surrogate identifier because no business key was recorded. Attributes are typed against abstract domains and carry no platform-specific length, precision or storage.

> Derived deterministically from `conceptual_model.json`. No AI was involved in this step: the conceptual model already carries the business judgement, and turning it into a normalized logical design is a set of transformation rules. Every design decision appears under Normalization or Assumptions.

# Logical Model Overview

- **Database:** datamodel
- **Subject areas:** 4
- **Entities:** 7 (6 fundamental, 0 dependent, 1 associative)
- **Attributes:** 54
- **Relationships:** 6 (2 identifying)
- **Normalization actions:** 5

# Subject Areas

## Customer Management

Core customer identity, contact information, and credit management.

**Entities:** Customer

## Product Catalog

Product definitions, inventory levels, and supplier relationships.

**Entities:** Product

## Order Fulfillment

Order creation, line item tracking, status, and shipping.

**Entities:** Order, Order Line Item, Order Product, Order Product Association

## Unassigned

Entities the conceptual model placed in no domain.

**Entities:** Order Item

# Logical Entities

## Customer

A party who places orders and purchases products. Identified by a unique customer code.

- **Kind:** Fundamental
- **Subject area:** Customer Management
- **Primary key:** customer_code
- **Alternate keys:** email; phone_number; postal_code
- **Derived from:** `bronze.customer`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| customer_code | Text | PK | Mandatory |  |
| first_name | Text |  | Optional |  |
| last_name | Text |  | Optional |  |
| email | Email | AK | Optional |  |
| phone_number | Text | AK | Optional |  |
| date_of_birth | Text |  | Optional |  |
| gender | Text |  | Optional |  |
| city | Text |  | Optional |  |
| state | Text |  | Optional |  |
| country | Text |  | Optional |  |
| postal_code | Text | AK | Optional |  |
| customer_status | Text |  | Optional |  |
| credit_limit | Text |  | Optional |  |
| is_active | Text |  | Optional |  |

## Order

A customer purchase transaction containing one or more products, with order status, payment details, and fulfillment tracking.

- **Kind:** Fundamental
- **Subject area:** Order Fulfillment
- **Primary key:** order_number
- **Derived from:** `bronze.orders`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| order_number | Text | PK | Mandatory |  |
| order_date | Text |  | Optional |  |
| order_status | Text |  | Optional |  |
| payment_method | Text |  | Optional |  |
| total_amount | Text |  | Optional |  |
| tax_amount | Text |  | Optional |  |
| discount_amount | Text |  | Optional |  |
| shipping_amount | Text |  | Optional |  |
| shipped_date | Text |  | Optional |  |
| remarks | Text |  | Optional |  |
| created_by | Text |  | Optional |  |
| created_date | Text |  | Optional |  |
| customer_code | Identifier | FK | Mandatory | Customer |

## Order Item

A denormalized order line containing product and pricing details. This entity appears to duplicate Order Product but retains product name as a text field rather than reference.

- **Kind:** Fundamental
- **Subject area:** Unassigned
- **Primary key:** order_item_id
- **Derived from:** `bronze.order_item`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| order_item_id | Text | PK | Mandatory |  |
| product_name | Text |  | Optional |  |
| quantity | Whole Number |  | Optional |  |
| unit_price | Text |  | Optional |  |
| total_price | Text |  | Optional |  |
| order_number | Identifier | FK | Mandatory | Order |

## Order Line Item

A line item within an order, capturing the product name, quantity ordered, and pricing at order time. Denormalizes product information at the point of order.

- **Kind:** Fundamental
- **Subject area:** Order Fulfillment
- **Primary key:** order_id, product_name
- **Derived from:** `bronze.order_item`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| order_id | Text | PK | Mandatory |  |
| product_name | Text | PK | Mandatory |  |
| quantity | Whole Number |  | Optional |  |
| unit_price | Text |  | Optional |  |
| total_price | Text |  | Optional |  |

## Order Product

A line item that links an order to a product with the quantity and selling price at the time of order. Serves as the transaction record for product fulfillment.

- **Kind:** Fundamental
- **Subject area:** Order Fulfillment
- **Primary key:** order_id, product_id
- **Derived from:** `bronze.order_product`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| order_id | Text | PK | Mandatory |  |
| product_id | Text | PK | Mandatory |  |
| quantity | Whole Number |  | Optional |  |
| selling_price | Text |  | Optional |  |
| product_code | Identifier | FK | Mandatory | Product |
| order_number | Identifier | FK | Mandatory | Order |

## Order Product Association

Resolves the many-to-many relationship between Order and Product. Each occurrence records that one Order references one Product.

- **Kind:** Associative
- **Subject area:** Order Fulfillment
- **Primary key:** order_number, product_code

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| order_number | Identifier | PK | Mandatory | Order |
| product_code | Identifier | PK | Mandatory | Product |

## Product

An item offered for sale. Tracked by product code, with inventory, pricing, category, and supplier information.

- **Kind:** Fundamental
- **Subject area:** Product Catalog
- **Primary key:** product_code
- **Derived from:** `bronze.product`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| product_code | Text | PK | Mandatory |  |
| product_name | Text |  | Optional |  |
| category | Text |  | Optional |  |
| price | Amount |  | Optional |  |
| stock_quantity | Text |  | Optional |  |
| supplier_name | Text |  | Optional |  |
| is_active | Text |  | Optional |  |
| created_date | Text |  | Optional |  |

# Entity Relationships

| Parent | Child | Cardinality | Optionality | Identifying | Foreign key |
|---|---|---|---|---|---|
| Customer | Order | one-to-many | Mandatory | No | customer_code |
| Order | Order Item | one-to-many | Mandatory | No | order_number |
| Order | Order Product | one-to-many | Mandatory | No | order_number |
| Order | Order Product Association | one-to-many | Mandatory | Yes | order_number |
| Product | Order Product | one-to-many | Mandatory | No | product_code |
| Product | Order Product Association | one-to-many | Mandatory | Yes | product_code |

# Normalization

Actions taken and checks performed while deriving the logical design. Checks that found nothing are listed too, so a compliant design is distinguishable from one that was never examined.

### 1NF — Order Product Association

**Resolved many-to-many between Order and Product.** A many-to-many relationship cannot be represented without a repeating group. An associative entity keyed on both parents removes the repetition and gives the relationship a place to carry its own attributes later.

### 2NF — Order Line Item

**Checked non-key attributes against the full composite key.** Order Line Item has a composite key, so every non-key attribute (quantity, unit_price, total_price) must depend on the whole key rather than part of it. No partial dependency was found.

### 2NF — Order Product

**Checked non-key attributes against the full composite key.** Order Product has a composite key, so every non-key attribute (quantity, selling_price) must depend on the whole key rather than part of it. No partial dependency was found.

### 3NF — Order Item

**Confirmed Order attributes are not repeated on Order Item.** Order Item references Order, which references Customer. The chain is already decomposed, so Customer's attributes reach Order Item by navigation rather than by duplication.

### 3NF — Order Product

**Confirmed Order attributes are not repeated on Order Product.** Order Product references Order, which references Customer. The chain is already decomposed, so Customer's attributes reach Order Product by navigation rather than by duplication.

# Assumptions

_None identified._
