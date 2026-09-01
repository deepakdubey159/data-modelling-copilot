# Executive Summary

Logical design for datamodel, derived from the conceptual model. 20 entities carry 23 relationships: 2 associative entities resolve many-to-many relationships and 2 entities are identified through a parent. 0 entities required a surrogate identifier because no business key was recorded. Attributes are typed against abstract domains and carry no platform-specific length, precision or storage.

> Derived deterministically from `conceptual_model.json`. No AI was involved in this step: the conceptual model already carries the business judgement, and turning it into a normalized logical design is a set of transformation rules. Every design decision appears under Normalization or Assumptions.

# Logical Model Overview

- **Database:** datamodel
- **Subject areas:** 6
- **Entities:** 20 (16 fundamental, 2 dependent, 2 associative)
- **Attributes:** 76
- **Relationships:** 23 (6 identifying)
- **Normalization actions:** 16

# Subject Areas

## Sales & Customer Management

Manages customers, their orders, and the sales representatives who service them.

**Entities:** Customer, Employee, Order

## Product & Inventory

Manages product catalog, supplier relationships, categories, and stock levels across warehouses.

**Entities:** Category, Inventory, Product, Product Promotion Association, Product Warehouse Association, Supplier, Warehouse

## Order Fulfillment

Manages the complete order lifecycle: line items, payments, shipments, and returns.

**Entities:** Order Item, Payment, Return Order, Shipment

## Promotions

Manages promotional campaigns and their associations with products.

**Entities:** Promotion

## Geography & Organization

Defines organizational structure, reporting hierarchies, and geographic locations.

**Entities:** City, Country, Department, State

## System Administration

Tracks data changes and system operations.

**Entities:** Audit Log

# Logical Entities

## Audit Log

A system record of data operations (INSERT, UPDATE, DELETE) for compliance and audit purposes.

- **Kind:** Fundamental
- **Subject area:** System Administration
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

A classification grouping related products together (e.g., Accessories, Storage).

- **Kind:** Fundamental
- **Subject area:** Product & Inventory
- **Primary key:** category_name
- **Derived from:** `bronze.category`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| category_name | Text | PK | Mandatory |  |

## City

A city or municipal area serving as a location for customers and warehouses.

- **Kind:** Fundamental
- **Subject area:** Geography & Organization
- **Primary key:** city_name
- **Derived from:** `bronze.city`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| city_name | Text | PK | Mandatory |  |
| state_name | Identifier | FK | Mandatory | State |

## Country

A nation recognized for business and geographic purposes.

- **Kind:** Fundamental
- **Subject area:** Geography & Organization
- **Primary key:** country_code
- **Derived from:** `bronze.country`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| country_code | Text | PK | Mandatory |  |
| country_name | Text |  | Optional |  |
| created_at | Text |  | Optional |  |

## Customer

A person or business entity that purchases products. Customers have credit limits and geographic locations.

- **Kind:** Fundamental
- **Subject area:** Sales & Customer Management
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
| city_name | Identifier | FK | Optional | City |

## Department

An organizational unit grouping employees by function.

- **Kind:** Fundamental
- **Subject area:** Geography & Organization
- **Primary key:** department_name
- **Derived from:** `bronze.department`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| department_name | Text | PK | Mandatory |  |

## Employee

A member of the organization who may be a sales representative or manager. Employees have departments and report to managers.

- **Kind:** Fundamental
- **Subject area:** Sales & Customer Management
- **Primary key:** email
- **Derived from:** `bronze.employee`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| email | Email | PK | Mandatory |  |
| first_name | Text |  | Optional |  |
| last_name | Text |  | Optional |  |
| salary | Amount |  | Optional |  |
| hire_date | Text |  | Optional |  |
| Parent email | Identifier | FK | Optional | Employee |
| department_name | Identifier | FK | Optional | Department |

## Inventory

The quantity of a product held at a specific warehouse, with reorder thresholds.

- **Kind:** Dependent
- **Subject area:** Product & Inventory
- **Primary key:** warehouse_name, product_sku
- **Derived from:** `bronze.inventory`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| warehouse_name | Text | PK | Mandatory | Warehouse |
| product_sku | Text | PK | Mandatory |  |
| quantity | Whole Number |  | Optional |  |
| reorder_level | Text |  | Optional |  |
| Product sku | Identifier | FK | Mandatory | Product |

## Order

A request by a customer to purchase products, recorded with order date and status. May be assigned to a sales representative.

- **Kind:** Fundamental
- **Subject area:** Sales & Customer Management
- **Primary key:** order_id
- **Derived from:** `bronze.orders`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| order_id | Text | PK | Mandatory |  |
| order_date | Text |  | Optional |  |
| order_status | Text |  | Optional |  |
| customer_number | Identifier | FK | Optional | Customer |
| Employee email | Identifier | FK | Optional | Employee |

## Order Item

A line item within an order, specifying a product, quantity, and unit price at the time of order.

- **Kind:** Dependent
- **Subject area:** Order Fulfillment
- **Primary key:** order_id, line_number
- **Derived from:** `bronze.order_item`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| order_id | Text | PK | Mandatory | Order |
| line_number | Text | PK | Mandatory |  |
| quantity | Whole Number |  | Optional |  |
| unit_price | Text |  | Optional |  |
| Product sku | Identifier | FK | Optional | Product |

## Payment

A financial transaction recording payment received for an order via a specified payment method.

- **Kind:** Fundamental
- **Subject area:** Order Fulfillment
- **Primary key:** payment_id
- **Derived from:** `bronze.payment`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| payment_id | Text | PK | Mandatory |  |
| payment_method | Text |  | Optional |  |
| payment_date | Text |  | Optional |  |
| amount | Amount |  | Optional |  |
| order_id | Identifier | FK | Optional | Order |

## Product

A tangible item offered for sale, with a SKU, unit price, category, and supplier. Has active/inactive status.

- **Kind:** Fundamental
- **Subject area:** Product & Inventory
- **Primary key:** sku
- **Derived from:** `bronze.product`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| sku | Code | PK | Mandatory |  |
| product_name | Text |  | Optional |  |
| unit_price | Text |  | Optional |  |
| status | Code |  | Optional |  |
| supplier_name | Identifier | FK | Optional | Supplier |
| category_name | Identifier | FK | Optional | Category |

## Product Promotion Association

Resolves the many-to-many relationship between Product and Promotion. Each occurrence records that one Product references one Promotion.

- **Kind:** Associative
- **Subject area:** Product & Inventory
- **Primary key:** Product sku, promotion_name

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| Product sku | Identifier | PK | Mandatory | Product |
| promotion_name | Identifier | PK | Mandatory | Promotion |

## Product Warehouse Association

Resolves the many-to-many relationship between Product and Warehouse. Each occurrence records that one Product references one Warehouse.

- **Kind:** Associative
- **Subject area:** Product & Inventory
- **Primary key:** Product sku, warehouse_name

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| Product sku | Identifier | PK | Mandatory | Product |
| warehouse_name | Identifier | PK | Mandatory | Warehouse |

## Promotion

A time-bound or product-bound marketing campaign offering a discount.

- **Kind:** Fundamental
- **Subject area:** Promotions
- **Primary key:** promotion_name
- **Derived from:** `bronze.promotion`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| promotion_name | Text | PK | Mandatory |  |
| discount_percent | Text |  | Optional |  |

## Return Order

A product return request tied to an original order, including the return reason.

- **Kind:** Fundamental
- **Subject area:** Order Fulfillment
- **Primary key:** return_id
- **Derived from:** `bronze.return_order`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| return_id | Text | PK | Mandatory |  |
| return_reason | Text |  | Optional |  |
| order_id | Identifier | FK | Optional | Order |
| Product sku | Identifier | FK | Optional | Product |

## Shipment

A fulfillment record tracking the dispatch of an order from a warehouse with a tracking number.

- **Kind:** Fundamental
- **Subject area:** Order Fulfillment
- **Primary key:** shipment_id
- **Alternate keys:** tracking_number
- **Derived from:** `bronze.shipment`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| shipment_id | Text | PK | Mandatory |  |
| shipped_date | Text |  | Optional |  |
| tracking_number | Text | AK | Optional |  |
| order_id | Identifier | FK | Optional | Order |
| warehouse_name | Identifier | FK | Optional | Warehouse |

## State

A provincial or state-level geographic subdivision of a country.

- **Kind:** Fundamental
- **Subject area:** Geography & Organization
- **Primary key:** state_name
- **Derived from:** `bronze.state`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| state_name | Text | PK | Mandatory |  |
| country_code | Identifier | FK | Mandatory | Country |

## Supplier

An external party that provides products to the business.

- **Kind:** Fundamental
- **Subject area:** Product & Inventory
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

A physical location where inventory is stored and orders are fulfilled.

- **Kind:** Fundamental
- **Subject area:** Product & Inventory
- **Primary key:** warehouse_name
- **Derived from:** `bronze.warehouse`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| warehouse_name | Text | PK | Mandatory |  |
| city_name | Identifier | FK | Optional | City |

# Entity Relationships

| Parent | Child | Cardinality | Optionality | Identifying | Foreign key |
|---|---|---|---|---|---|
| Category | Product | one-to-many | Optional | No | category_name |
| City | Customer | one-to-many | Optional | No | city_name |
| City | Warehouse | one-to-many | Optional | No | city_name |
| Country | State | one-to-many | Mandatory | No | country_code |
| Customer | Order | one-to-many | Optional | No | customer_number |
| Department | Employee | one-to-many | Optional | No | department_name |
| Employee | Employee | one-to-many | Optional | No | Parent email |
| Employee | Order | one-to-many | Optional | No | Employee email |
| Order | Order Item | one-to-many | Mandatory | Yes | order_id |
| Order | Payment | one-to-many | Optional | No | order_id |
| Order | Return Order | one-to-many | Optional | No | order_id |
| Order | Shipment | one-to-many | Optional | No | order_id |
| Product | Inventory | one-to-many | Mandatory | No | Product sku |
| Product | Order Item | one-to-many | Optional | No | Product sku |
| Product | Product Promotion Association | one-to-many | Mandatory | Yes | Product sku |
| Product | Product Warehouse Association | one-to-many | Mandatory | Yes | Product sku |
| Product | Return Order | one-to-many | Optional | No | Product sku |
| Promotion | Product Promotion Association | one-to-many | Mandatory | Yes | promotion_name |
| State | City | one-to-many | Mandatory | No | state_name |
| Supplier | Product | one-to-many | Optional | No | supplier_name |
| Warehouse | Inventory | one-to-many | Mandatory | Yes | warehouse_name |
| Warehouse | Product Warehouse Association | one-to-many | Mandatory | Yes | warehouse_name |
| Warehouse | Shipment | one-to-many | Optional | No | warehouse_name |

# Normalization

Actions taken and checks performed while deriving the logical design. Checks that found nothing are listed too, so a compliant design is distinguishable from one that was never examined.

### 1NF — Product Promotion Association

**Resolved many-to-many between Product and Promotion.** A many-to-many relationship cannot be represented without a repeating group. An associative entity keyed on both parents removes the repetition and gives the relationship a place to carry its own attributes later.

### 1NF — Product Warehouse Association

**Resolved many-to-many between Product and Warehouse.** A many-to-many relationship cannot be represented without a repeating group. An associative entity keyed on both parents removes the repetition and gives the relationship a place to carry its own attributes later.

### 2NF — Inventory

**Checked non-key attributes against the full composite key.** Inventory has a composite key, so every non-key attribute (quantity, reorder_level) must depend on the whole key rather than part of it. No partial dependency was found.

### 2NF — Inventory

**Identified Inventory as dependent on Warehouse.** Its business key includes Warehouse's key (warehouse_name), so it cannot be identified independently. The relationship is identifying and the key is propagated rather than duplicated.

### 2NF — Order Item

**Checked non-key attributes against the full composite key.** Order Item has a composite key, so every non-key attribute (quantity, unit_price) must depend on the whole key rather than part of it. No partial dependency was found.

### 2NF — Order Item

**Identified Order Item as dependent on Order.** Its business key includes Order's key (order_id), so it cannot be identified independently. The relationship is identifying and the key is propagated rather than duplicated.

### 3NF — City

**Confirmed State attributes are not repeated on City.** City references State, which references Country. The chain is already decomposed, so Country's attributes reach City by navigation rather than by duplication.

### 3NF — Customer

**Confirmed City attributes are not repeated on Customer.** Customer references City, which references State. The chain is already decomposed, so State's attributes reach Customer by navigation rather than by duplication.

### 3NF — Inventory

**Confirmed Warehouse attributes are not repeated on Inventory.** Inventory references Warehouse, which references City. The chain is already decomposed, so City's attributes reach Inventory by navigation rather than by duplication.

### 3NF — Order

**Confirmed Employee attributes are not repeated on Order.** Order references Employee, which references Department. The chain is already decomposed, so Department's attributes reach Order by navigation rather than by duplication.

### 3NF — Order Item

**Confirmed Product attributes are not repeated on Order Item.** Order Item references Product, which references Category. The chain is already decomposed, so Category's attributes reach Order Item by navigation rather than by duplication.

### 3NF — Payment

**Confirmed Order attributes are not repeated on Payment.** Payment references Order, which references Employee. The chain is already decomposed, so Employee's attributes reach Payment by navigation rather than by duplication.

### 3NF — Product Warehouse Association

**Confirmed Warehouse attributes are not repeated on Product Warehouse Association.** Product Warehouse Association references Warehouse, which references City. The chain is already decomposed, so City's attributes reach Product Warehouse Association by navigation rather than by duplication.

### 3NF — Return Order

**Confirmed Product attributes are not repeated on Return Order.** Return Order references Product, which references Category. The chain is already decomposed, so Category's attributes reach Return Order by navigation rather than by duplication.

### 3NF — Shipment

**Confirmed Warehouse attributes are not repeated on Shipment.** Shipment references Warehouse, which references City. The chain is already decomposed, so City's attributes reach Shipment by navigation rather than by duplication.

### 3NF — Warehouse

**Confirmed City attributes are not repeated on Warehouse.** Warehouse references City, which references State. The chain is already decomposed, so State's attributes reach Warehouse by navigation rather than by duplication.

# Assumptions

_None identified._
