# Executive Summary

Logical design for datamodel, derived from the conceptual model. 18 entities carry 0 relationships: 0 associative entities resolve many-to-many relationships and 0 entities are identified through a parent. 0 entities required a surrogate identifier because no business key was recorded. Attributes are typed against abstract domains and carry no platform-specific length, precision or storage.

> Derived deterministically from `conceptual_model.json`. No AI was involved in this step: the conceptual model already carries the business judgement, and turning it into a normalized logical design is a set of transformation rules. Every design decision appears under Normalization or Assumptions.

# Logical Model Overview

- **Database:** datamodel
- **Subject areas:** 7
- **Entities:** 18 (18 fundamental, 0 dependent, 0 associative)
- **Attributes:** 57
- **Relationships:** 0 (0 identifying)
- **Normalization actions:** 2

# Subject Areas

## Geographic Reference

Master data for locations including countries, states, and cities used throughout the system.

**Entities:** City, Country, State

## Product Catalog

Product master data including categories, suppliers, pricing, and promotion management.

**Entities:** Category, Product, Promotion, Supplier

## Sales

Customer orders and sales transactions including order placement, line items, and payment processing.

**Entities:** Customer, Order, Order Line Item, Payment

## Inventory

Warehouse and stock management across distribution facilities.

**Entities:** Inventory, Warehouse

## Fulfillment

Order fulfillment operations including shipment and return processing.

**Entities:** Return Order, Shipment

## Organization

Internal employee and department structure.

**Entities:** Department, Employee

## Audit & Compliance

System audit logging and change tracking.

**Entities:** Audit Log

# Logical Entities

## Audit Log

System audit trail recording all database changes for compliance and troubleshooting.

- **Kind:** Fundamental
- **Subject area:** Audit & Compliance
- **Primary key:** audit_id
- **Derived from:** `bronze.audit_log`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| audit_id | Text | PK | Mandatory |  |
| table_name | Text |  | Optional |  |
| operation | Code |  | Optional |  |
| user_name | Text |  | Optional |  |
| operation_timestamp | Text |  | Optional |  |

## Category

A product category for grouping related products.

- **Kind:** Fundamental
- **Subject area:** Product Catalog
- **Primary key:** category_name
- **Derived from:** `bronze.category`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| category_name | Text | PK | Mandatory |  |

## City

A city within a state.

- **Kind:** Fundamental
- **Subject area:** Geographic Reference
- **Primary key:** city_name, state_id
- **Derived from:** `bronze.city`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| city_name | Text | PK | Mandatory |  |
| state_id | Text | PK | Mandatory |  |

## Country

A country representing a geographic region and market for the business.

- **Kind:** Fundamental
- **Subject area:** Geographic Reference
- **Primary key:** country_code
- **Derived from:** `bronze.country`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| country_code | Text | PK | Mandatory |  |
| country_name | Text |  | Optional |  |
| created_at | Text |  | Optional |  |

## Customer

A person or organization that purchases products from the business.

- **Kind:** Fundamental
- **Subject area:** Sales
- **Primary key:** customer_number
- **Alternate keys:** email
- **Derived from:** `bronze.customer`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| customer_number | Text | PK | Mandatory |  |
| first_name | Text |  | Optional |  |
| last_name | Text |  | Optional |  |
| email | Email | AK | Optional |  |
| phone | Phone |  | Optional |  |
| credit_limit | Text |  | Optional |  |
| status | Code |  | Optional |  |

## Department

An organizational department within the company.

- **Kind:** Fundamental
- **Subject area:** Organization
- **Primary key:** department_name
- **Derived from:** `bronze.department`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| department_name | Text | PK | Mandatory |  |

## Employee

A person employed by the company, potentially in a sales or support capacity.

- **Kind:** Fundamental
- **Subject area:** Organization
- **Primary key:** email
- **Derived from:** `bronze.employee`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| email | Email | PK | Mandatory |  |
| first_name | Text |  | Optional |  |
| last_name | Text |  | Optional |  |
| salary | Amount |  | Optional |  |
| hire_date | Text |  | Optional |  |

## Inventory

The stock level of a specific product at a specific warehouse, including reorder thresholds.

- **Kind:** Fundamental
- **Subject area:** Inventory
- **Primary key:** warehouse_id, product_id
- **Derived from:** `bronze.inventory`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| warehouse_id | Text | PK | Mandatory |  |
| product_id | Text | PK | Mandatory |  |
| quantity | Whole Number |  | Optional |  |
| reorder_level | Text |  | Optional |  |

## Order

A customer's purchase request for one or more products.

- **Kind:** Fundamental
- **Subject area:** Sales
- **Primary key:** order_id
- **Derived from:** `bronze.orders`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| order_id | Text | PK | Mandatory |  |
| order_date | Text |  | Optional |  |
| order_status | Text |  | Optional |  |

## Order Line Item

A line item within an order specifying a product, quantity, and price.

- **Kind:** Fundamental
- **Subject area:** Sales
- **Primary key:** order_id, line_number
- **Derived from:** `bronze.order_item`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| order_id | Text | PK | Mandatory |  |
| line_number | Text | PK | Mandatory |  |
| quantity | Whole Number |  | Optional |  |
| unit_price | Text |  | Optional |  |

## Payment

A payment transaction for a customer order.

- **Kind:** Fundamental
- **Subject area:** Sales
- **Primary key:** payment_id
- **Derived from:** `bronze.payment`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| payment_id | Text | PK | Mandatory |  |
| payment_method | Text |  | Optional |  |
| payment_date | Text |  | Optional |  |
| amount | Amount |  | Optional |  |

## Product

A tangible good offered for sale by the business.

- **Kind:** Fundamental
- **Subject area:** Product Catalog
- **Primary key:** sku
- **Derived from:** `bronze.product`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| sku | Code | PK | Mandatory |  |
| product_name | Text |  | Optional |  |
| unit_price | Text |  | Optional |  |
| status | Code |  | Optional |  |

## Promotion

A discount or promotional offer that can be applied to products.

- **Kind:** Fundamental
- **Subject area:** Product Catalog
- **Primary key:** promotion_name
- **Derived from:** `bronze.promotion`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| promotion_name | Text | PK | Mandatory |  |
| discount_percent | Text |  | Optional |  |

## Return Order

A return request for products from a completed order.

- **Kind:** Fundamental
- **Subject area:** Fulfillment
- **Primary key:** return_id
- **Derived from:** `bronze.return_order`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| return_id | Text | PK | Mandatory |  |
| return_reason | Text |  | Optional |  |

## Shipment

The fulfillment and delivery of an order from a warehouse.

- **Kind:** Fundamental
- **Subject area:** Fulfillment
- **Primary key:** shipment_id
- **Alternate keys:** tracking_number
- **Derived from:** `bronze.shipment`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| shipment_id | Text | PK | Mandatory |  |
| shipped_date | Text |  | Optional |  |
| tracking_number | Text | AK | Optional |  |

## State

A state or province within a country.

- **Kind:** Fundamental
- **Subject area:** Geographic Reference
- **Primary key:** state_name, country_id
- **Derived from:** `bronze.state`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| state_name | Text | PK | Mandatory |  |
| country_id | Text | PK | Mandatory |  |

## Supplier

A vendor who supplies products to the business.

- **Kind:** Fundamental
- **Subject area:** Product Catalog
- **Primary key:** supplier_name
- **Alternate keys:** email
- **Derived from:** `bronze.supplier`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| supplier_name | Text | PK | Mandatory |  |
| contact_name | Text |  | Optional |  |
| email | Email | AK | Optional |  |
| phone | Phone |  | Optional |  |

## Warehouse

A storage facility that holds inventory and fulfills orders.

- **Kind:** Fundamental
- **Subject area:** Inventory
- **Primary key:** warehouse_name
- **Derived from:** `bronze.warehouse`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| warehouse_name | Text | PK | Mandatory |  |

# Entity Relationships

_No relationships identified._

# Normalization

Actions taken and checks performed while deriving the logical design. Checks that found nothing are listed too, so a compliant design is distinguishable from one that was never examined.

### 2NF — Inventory

**Checked non-key attributes against the full composite key.** Inventory has a composite key, so every non-key attribute (quantity, reorder_level) must depend on the whole key rather than part of it. No partial dependency was found.

### 2NF — Order Line Item

**Checked non-key attributes against the full composite key.** Order Line Item has a composite key, so every non-key attribute (quantity, unit_price) must depend on the whole key rather than part of it. No partial dependency was found.

# Assumptions

_None identified._
