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

## Geography

Organizational and operational locations: countries, states, cities, and warehouses.

**Entities:** City, Country, State, Warehouse

## Catalog & Supply

Product information, categorization, supplier relationships, and pricing.

**Entities:** Category, Product, Promotion, Supplier

## Sales & Orders

Customer order lifecycle from placement through delivery and payment.

**Entities:** Order, Order Item, Payment, Shipment

## Inventory Management

Stock levels, warehouse distribution, and product availability across locations.

**Entities:** Inventory

## Customer Management

Customer profiles and relationships.

**Entities:** Customer

## Organization

Internal organizational structure: employees, departments, and reporting relationships.

**Entities:** Department, Employee

## Operations

Return handling and system audit trails.

**Entities:** Audit Log, Return

# Logical Entities

## Audit Log

A system record of data changes including inserts, updates, and deletes.

- **Kind:** Fundamental
- **Subject area:** Operations
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

A classification or grouping of related products.

- **Kind:** Fundamental
- **Subject area:** Catalog & Supply
- **Primary key:** category_name
- **Derived from:** `bronze.category`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| category_name | Text | PK | Mandatory |  |

## City

A city or municipality within a state.

- **Kind:** Fundamental
- **Subject area:** Geography
- **Primary key:** city_name, state_name
- **Derived from:** `bronze.city`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| city_name | Text | PK | Mandatory |  |
| state_name | Text | PK | Mandatory |  |

## Country

A nation or sovereign territory where the organization operates.

- **Kind:** Fundamental
- **Subject area:** Geography
- **Primary key:** country_code
- **Derived from:** `bronze.country`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| country_code | Text | PK | Mandatory |  |
| country_name | Text |  | Optional |  |
| created_at | Text |  | Optional |  |

## Customer

An individual or organization that purchases products.

- **Kind:** Fundamental
- **Subject area:** Customer Management
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

An organizational unit within the company.

- **Kind:** Fundamental
- **Subject area:** Organization
- **Primary key:** department_name
- **Derived from:** `bronze.department`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| department_name | Text | PK | Mandatory |  |

## Employee

A person employed by the organization.

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

The quantity of a product held in a warehouse, including reorder threshold.

- **Kind:** Fundamental
- **Subject area:** Inventory Management
- **Primary key:** warehouse_name, sku
- **Derived from:** `bronze.inventory`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| warehouse_name | Text | PK | Mandatory |  |
| sku | Code | PK | Mandatory |  |
| quantity | Whole Number |  | Optional |  |
| reorder_level | Text |  | Optional |  |

## Order

A customer purchase order for one or more products.

- **Kind:** Fundamental
- **Subject area:** Sales & Orders
- **Primary key:** order_id
- **Derived from:** `bronze.orders`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| order_id | Text | PK | Mandatory |  |
| order_date | Text |  | Optional |  |
| order_status | Text |  | Optional |  |

## Order Item

A line item within an order specifying product, quantity, and price.

- **Kind:** Fundamental
- **Subject area:** Sales & Orders
- **Primary key:** order_id, line_number
- **Derived from:** `bronze.order_item`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| order_id | Text | PK | Mandatory |  |
| line_number | Text | PK | Mandatory |  |
| quantity | Whole Number |  | Optional |  |
| unit_price | Text |  | Optional |  |

## Payment

A payment transaction related to an order.

- **Kind:** Fundamental
- **Subject area:** Sales & Orders
- **Primary key:** payment_id
- **Derived from:** `bronze.payment`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| payment_id | Text | PK | Mandatory |  |
| payment_method | Text |  | Optional |  |
| payment_date | Text |  | Optional |  |
| amount | Amount |  | Optional |  |

## Product

A physical or digital good offered for sale.

- **Kind:** Fundamental
- **Subject area:** Catalog & Supply
- **Primary key:** sku
- **Derived from:** `bronze.product`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| sku | Code | PK | Mandatory |  |
| product_name | Text |  | Optional |  |
| unit_price | Text |  | Optional |  |
| status | Code |  | Optional |  |

## Promotion

A discount or marketing offer applied to products.

- **Kind:** Fundamental
- **Subject area:** Catalog & Supply
- **Primary key:** promotion_name
- **Derived from:** `bronze.promotion`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| promotion_name | Text | PK | Mandatory |  |
| discount_percent | Text |  | Optional |  |

## Return

A product returned by a customer from a completed order.

- **Kind:** Fundamental
- **Subject area:** Operations
- **Primary key:** return_id
- **Derived from:** `bronze.return_order`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| return_id | Text | PK | Mandatory |  |
| return_reason | Text |  | Optional |  |

## Shipment

A dispatch of ordered items from a warehouse to a customer.

- **Kind:** Fundamental
- **Subject area:** Sales & Orders
- **Primary key:** tracking_number
- **Derived from:** `bronze.shipment`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| tracking_number | Text | PK | Mandatory |  |
| shipped_date | Text |  | Optional |  |

## State

A state or province within a country.

- **Kind:** Fundamental
- **Subject area:** Geography
- **Primary key:** state_name, country_code
- **Derived from:** `bronze.state`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| state_name | Text | PK | Mandatory |  |
| country_code | Text | PK | Mandatory |  |

## Supplier

A vendor or partner from whom products are sourced.

- **Kind:** Fundamental
- **Subject area:** Catalog & Supply
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

A physical storage and distribution facility.

- **Kind:** Fundamental
- **Subject area:** Geography
- **Primary key:** warehouse_name, city_name
- **Derived from:** `bronze.warehouse`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| warehouse_name | Text | PK | Mandatory |  |
| city_name | Text | PK | Mandatory |  |

# Entity Relationships

_No relationships identified._

# Normalization

Actions taken and checks performed while deriving the logical design. Checks that found nothing are listed too, so a compliant design is distinguishable from one that was never examined.

### 2NF — Inventory

**Checked non-key attributes against the full composite key.** Inventory has a composite key, so every non-key attribute (quantity, reorder_level) must depend on the whole key rather than part of it. No partial dependency was found.

### 2NF — Order Item

**Checked non-key attributes against the full composite key.** Order Item has a composite key, so every non-key attribute (quantity, unit_price) must depend on the whole key rather than part of it. No partial dependency was found.

# Assumptions

_None identified._
