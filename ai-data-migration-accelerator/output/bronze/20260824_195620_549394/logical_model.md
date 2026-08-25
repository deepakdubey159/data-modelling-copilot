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

Master data for geographic locations used to locate customers, warehouses, and suppliers.

**Entities:** City, Country, State

## Organization

Internal organizational structure including departments and employee hierarchy.

**Entities:** Department, Employee

## Product Catalog

Product master data including suppliers, categories, and promotional offers.

**Entities:** Category, Product, Promotion, Supplier

## Inventory

Inventory levels and reorder management across warehouse locations.

**Entities:** Inventory, Warehouse

## Sales

Customer acquisition, order management, and payment processing.

**Entities:** Customer, Order, Order Line, Payment

## Fulfillment

Order shipment and return management.

**Entities:** Return, Shipment

## Unassigned

Entities the conceptual model placed in no domain.

**Entities:** Audit Log

# Logical Entities

## Audit Log

A record of system changes tracking who performed what operation on which table and when.

- **Kind:** Fundamental
- **Subject area:** Unassigned
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

A classification grouping related products for merchandising and inventory management.

- **Kind:** Fundamental
- **Subject area:** Product Catalog
- **Primary key:** category_name
- **Derived from:** `bronze.category`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| category_name | Text | PK | Mandatory |  |

## City

A municipality or city within a state.

- **Kind:** Fundamental
- **Subject area:** Geography
- **Primary key:** city_name, state_name
- **Derived from:** `bronze.city`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| city_name | Text | PK | Mandatory |  |
| state_name | Text | PK | Mandatory |  |

## Country

A sovereign nation or territory where the business operates.

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

An organizational unit grouping employees by function.

- **Kind:** Fundamental
- **Subject area:** Organization
- **Primary key:** department_name
- **Derived from:** `bronze.department`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| department_name | Text | PK | Mandatory |  |

## Employee

A person employed by the organization with a role, compensation, and reporting structure.

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

Stock levels of a product at a specific warehouse, including reorder thresholds.

- **Kind:** Fundamental
- **Subject area:** Inventory
- **Primary key:** warehouse_name, sku
- **Derived from:** `bronze.inventory`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| warehouse_name | Text | PK | Mandatory |  |
| sku | Code | PK | Mandatory |  |
| quantity | Whole Number |  | Optional |  |
| reorder_level | Text |  | Optional |  |

## Order

A customer's request to purchase products, captured at a point in time and assigned a status.

- **Kind:** Fundamental
- **Subject area:** Sales
- **Primary key:** order_id
- **Derived from:** `bronze.orders`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| order_id | Text | PK | Mandatory |  |
| order_date | Text |  | Optional |  |
| order_status | Text |  | Optional |  |

## Order Line

A single product line within an order, specifying quantity and price.

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

A financial transaction recorded against an order.

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

A tangible item offered for sale to customers.

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

A time-limited marketing offer providing a discount on one or more products.

- **Kind:** Fundamental
- **Subject area:** Product Catalog
- **Primary key:** promotion_name
- **Derived from:** `bronze.promotion`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| promotion_name | Text | PK | Mandatory |  |
| discount_percent | Text |  | Optional |  |

## Return

A customer request to return a product from an order, including a reason.

- **Kind:** Fundamental
- **Subject area:** Fulfillment
- **Primary key:** return_id
- **Derived from:** `bronze.return_order`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| return_id | Text | PK | Mandatory |  |
| return_reason | Text |  | Optional |  |

## Shipment

A fulfillment event moving ordered products from a warehouse to a customer.

- **Kind:** Fundamental
- **Subject area:** Fulfillment
- **Primary key:** tracking_number
- **Derived from:** `bronze.shipment`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| tracking_number | Text | PK | Mandatory |  |
| shipped_date | Text |  | Optional |  |

## State

A geographic subdivision within a country.

- **Kind:** Fundamental
- **Subject area:** Geography
- **Primary key:** state_name, country_code
- **Derived from:** `bronze.state`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| state_name | Text | PK | Mandatory |  |
| country_code | Text | PK | Mandatory |  |

## Supplier

An external vendor providing products to the business.

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

A physical location where inventory is stored and fulfilled.

- **Kind:** Fundamental
- **Subject area:** Inventory
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

### 2NF — Order Line

**Checked non-key attributes against the full composite key.** Order Line has a composite key, so every non-key attribute (quantity, unit_price) must depend on the whole key rather than part of it. No partial dependency was found.

# Assumptions

_None identified._
