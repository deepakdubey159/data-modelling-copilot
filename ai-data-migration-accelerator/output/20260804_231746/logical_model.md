# Executive Summary

Logical design for datamodel, derived from the conceptual model. 19 entities carry 21 relationships: 1 associative entities resolve many-to-many relationships and 2 entities are identified through a parent. 0 entities required a surrogate identifier because no business key was recorded. Attributes are typed against abstract domains and carry no platform-specific length, precision or storage.

> Derived deterministically from `business_model.json`. No AI was involved in this step: the conceptual model already carries the business judgement, and turning it into a normalized logical design is a set of transformation rules. Every design decision appears under Normalization or Assumptions.

# Logical Model Overview

- **Database:** datamodel
- **Subject areas:** 6
- **Entities:** 19 (16 fundamental, 2 dependent, 1 associative)
- **Attributes:** 72
- **Relationships:** 21 (5 identifying)
- **Normalization actions:** 15

# Subject Areas

## Customer and Sales

The demand side of the business: who buys, what they ordered, and how they paid. This is the commercial heart of the model and the most heavily connected part of the schema.

**Entities:** Customer, Order Line, Payment, Sales Order

## Product and Sourcing

The catalogue of sellable goods, how it is organised for browsing, who supplies it, and the promotional offers applied to it.

**Entities:** Product, Product Category, Product Promotion Association, Promotion, Supplier

## Inventory and Fulfilment

Where goods are physically held and how they reach the customer or come back. Covers stock positions per location, outbound shipments, and returned goods.

**Entities:** Product Return, Shipment, Stock Level, Warehouse

## Workforce

The internal organisation. Employees are servicing accounts as sales representatives and are arranged in a reporting hierarchy within departments.

**Entities:** Department, Employee

## Geography

A shared three-level location hierarchy used as reference data by both customers and warehouses. It is not owned by any one business process.

**Entities:** City, Country, State

## Governance

Change tracking. Records that a data-modifying operation occurred, who performed it and when.

**Entities:** Audit Entry

# Logical Entities

## Audit Entry

A record that a data-modifying operation took place, capturing which record type was affected, what kind of change it was, who made it and when. It refers to other records by name rather than by a modelled relationship, so it stands apart from the rest of the model.

- **Kind:** Fundamental
- **Subject area:** Governance
- **Primary key:** Audit Reference
- **Derived from:** `bronze.audit_log`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| Audit Reference | Identifier | PK | Mandatory |  |
| Affected Record Type | Code |  | Optional |  |
| Operation Performed | Code |  | Optional |  |
| Performed By | Text |  | Optional |  |
| Performed At | Timestamp |  | Optional |  |

## City

A populated place, the lowest level of the shared location hierarchy.

- **Kind:** Fundamental
- **Subject area:** Geography
- **Primary key:** City Name
- **Derived from:** `bronze.city`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| City Name | Text | PK | Mandatory |  |
| State Name | Identifier | FK | Mandatory | State |

## Country

A sovereign country, the top of the location hierarchy, held with a short standard code as well as a name.

- **Kind:** Fundamental
- **Subject area:** Geography
- **Primary key:** Country Code
- **Derived from:** `bronze.country`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| Country Code | Code | PK | Mandatory |  |
| Country Name | Text |  | Optional |  |
| Date Recorded | Date |  | Optional |  |

## Customer

A person or organisation that buys from the business. Customers carry a credit limit, which indicates that trade is extended on account rather than strictly prepaid, and a lifecycle status.

- **Kind:** Fundamental
- **Subject area:** Customer and Sales
- **Primary key:** Customer Number
- **Alternate keys:** Email Address; Telephone Number
- **Derived from:** `bronze.customer`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| Customer Number | Identifier | PK | Mandatory |  |
| First Name | Text |  | Optional |  |
| Last Name | Text |  | Optional |  |
| Email Address | Email | AK | Optional |  |
| Telephone Number | Phone | AK | Optional |  |
| Credit Limit | Amount |  | Optional |  |
| Account Status | Code |  | Optional |  |
| City Name | Identifier | FK | Optional | City |

## Department

An organisational unit that employees are assigned to.

- **Kind:** Fundamental
- **Subject area:** Workforce
- **Primary key:** Department Name
- **Derived from:** `bronze.department`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| Department Name | Text | PK | Mandatory |  |

## Employee

A person employed by the business. Employees are organised in a management hierarchy and are the salespeople attributed to orders.

- **Kind:** Fundamental
- **Subject area:** Workforce
- **Primary key:** Email Address
- **Derived from:** `bronze.employee`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| Email Address | Email | PK | Mandatory |  |
| First Name | Text |  | Optional |  |
| Last Name | Text |  | Optional |  |
| Salary | Amount |  | Optional |  |
| Hire Date | Date |  | Optional |  |
| Parent Email Address | Identifier | FK | Optional | Employee |
| Department Name | Identifier | FK | Optional | Department |

## Order Line

One product on one order, at the price agreed at the time of ordering. It is identified by its position within the order rather than by a key of its own, which makes it dependent on the order for its existence.

- **Kind:** Dependent
- **Subject area:** Customer and Sales
- **Primary key:** Order Number, Line Number
- **Derived from:** `bronze.order_item`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| Order Number | Identifier | PK | Mandatory | Sales Order |
| Line Number | Whole Number | PK | Mandatory |  |
| Quantity Ordered | Whole Number |  | Optional |  |
| Agreed Unit Price | Amount |  | Optional |  |
| Product Stock Keeping Unit | Identifier | FK | Optional | Product |

## Payment

Money received against an order, recorded with the method used and the date it was taken.

- **Kind:** Fundamental
- **Subject area:** Customer and Sales
- **Primary key:** Payment Reference
- **Derived from:** `bronze.payment`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| Payment Reference | Identifier | PK | Mandatory |  |
| Payment Method | Code |  | Optional |  |
| Payment Date | Date |  | Optional |  |
| Amount Paid | Amount |  | Optional |  |
| Order Number | Identifier | FK | Optional | Sales Order |

## Product

An item the business sells. Products are catalogued, sourced from a supplier, priced, stocked in warehouses and may be promoted.

- **Kind:** Fundamental
- **Subject area:** Product and Sourcing
- **Primary key:** Stock Keeping Unit
- **Derived from:** `bronze.product`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| Stock Keeping Unit | Code | PK | Mandatory |  |
| Product Name | Text |  | Optional |  |
| List Unit Price | Amount |  | Optional |  |
| Product Status | Code |  | Optional |  |
| Category Name | Identifier | FK | Optional | Product Category |
| Supplier Name | Identifier | FK | Optional | Supplier |

## Product Category

A grouping used to organise the catalogue for browsing and reporting. The structure is flat, with no sub-categories.

- **Kind:** Fundamental
- **Subject area:** Product and Sourcing
- **Primary key:** Category Name
- **Derived from:** `bronze.category`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| Category Name | Text | PK | Mandatory |  |

## Product Promotion Association

Resolves the many-to-many relationship between Product and Promotion. Each occurrence records that one Product is promoted by one Promotion.

- **Kind:** Associative
- **Subject area:** Product and Sourcing
- **Primary key:** Product Stock Keeping Unit, Promotion Name

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| Product Stock Keeping Unit | Identifier | PK | Mandatory | Product |
| Promotion Name | Identifier | PK | Mandatory | Promotion |

## Product Return

Goods sent back by a customer after an order, recorded with the reason given.

- **Kind:** Fundamental
- **Subject area:** Inventory and Fulfilment
- **Primary key:** Return Reference
- **Derived from:** `bronze.return_order`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| Return Reference | Identifier | PK | Mandatory |  |
| Return Reason | Code |  | Optional |  |
| Order Number | Identifier | FK | Optional | Sales Order |
| Product Stock Keeping Unit | Identifier | FK | Optional | Product |

## Promotion

A discount offer applied to a set of products, expressed as a percentage reduction.

- **Kind:** Fundamental
- **Subject area:** Product and Sourcing
- **Primary key:** Promotion Name
- **Derived from:** `bronze.promotion`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| Promotion Name | Text | PK | Mandatory |  |
| Discount Percentage | Percentage |  | Optional |  |

## Sales Order

A customer's request to buy goods. The central transaction of the business: it links the buyer, the salesperson, the goods ordered, the money received, the dispatch, and any return.

- **Kind:** Fundamental
- **Subject area:** Customer and Sales
- **Primary key:** Order Number
- **Derived from:** `bronze.orders`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| Order Number | Identifier | PK | Mandatory |  |
| Order Date | Date |  | Optional |  |
| Order Status | Code |  | Optional |  |
| Customer Number | Identifier | FK | Optional | Customer |
| Employee Email Address | Identifier | FK | Optional | Employee |

## Shipment

A dispatch of goods from a warehouse to fulfil an order, carrying a tracking reference that lets the customer follow it.

- **Kind:** Fundamental
- **Subject area:** Inventory and Fulfilment
- **Primary key:** Tracking Number
- **Derived from:** `bronze.shipment`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| Tracking Number | Identifier | PK | Mandatory |  |
| Shipped Date | Date |  | Optional |  |
| Order Number | Identifier | FK | Optional | Sales Order |
| Warehouse Name | Identifier | FK | Optional | Warehouse |

## State

A state or province, the middle level of the location hierarchy.

- **Kind:** Fundamental
- **Subject area:** Geography
- **Primary key:** State Name
- **Derived from:** `bronze.state`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| State Name | Text | PK | Mandatory |  |
| Country Code | Identifier | FK | Mandatory | Country |

## Stock Level

How much of one product is held at one warehouse, together with the threshold at which it should be replenished. This is a business fact in its own right rather than a simple link, because it carries measures the business acts on.

- **Kind:** Dependent
- **Subject area:** Inventory and Fulfilment
- **Primary key:** Warehouse Name, Stock Keeping Unit
- **Derived from:** `bronze.inventory`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| Warehouse Name | Text | PK | Mandatory | Warehouse |
| Stock Keeping Unit | Code | PK | Mandatory | Product |
| Quantity On Hand | Whole Number |  | Optional |  |
| Reorder Level | Whole Number |  | Optional |  |

## Supplier

An external organisation that provides goods to the business, held with a named contact and direct contact details.

- **Kind:** Fundamental
- **Subject area:** Product and Sourcing
- **Primary key:** Supplier Name
- **Alternate keys:** Email Address; Telephone Number
- **Derived from:** `bronze.supplier`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| Supplier Name | Text | PK | Mandatory |  |
| Contact Name | Text |  | Optional |  |
| Email Address | Email | AK | Optional |  |
| Telephone Number | Phone | AK | Optional |  |

## Warehouse

A physical location where goods are held and from which orders are dispatched.

- **Kind:** Fundamental
- **Subject area:** Inventory and Fulfilment
- **Primary key:** Warehouse Name
- **Derived from:** `bronze.warehouse`

| Attribute | Domain | Key | Optionality | References |
|---|---|---|---|---|
| Warehouse Name | Text | PK | Mandatory |  |
| City Name | Identifier | FK | Optional | City |

# Entity Relationships

| Parent | Child | Cardinality | Optionality | Identifying | Foreign key |
|---|---|---|---|---|---|
| City | Customer | one-to-many | Optional | No | City Name |
| City | Warehouse | one-to-many | Optional | No | City Name |
| Country | State | one-to-many | Mandatory | No | Country Code |
| Customer | Sales Order | one-to-many | Optional | No | Customer Number |
| Department | Employee | one-to-many | Optional | No | Department Name |
| Employee | Employee | one-to-many | Optional | No | Parent Email Address |
| Employee | Sales Order | one-to-many | Optional | No | Employee Email Address |
| Product | Order Line | one-to-many | Optional | No | Product Stock Keeping Unit |
| Product | Product Promotion Association | one-to-many | Mandatory | Yes | Product Stock Keeping Unit |
| Product | Product Return | one-to-many | Optional | No | Product Stock Keeping Unit |
| Product | Stock Level | one-to-many | Optional | Yes | Stock Keeping Unit |
| Product Category | Product | one-to-many | Optional | No | Category Name |
| Promotion | Product Promotion Association | one-to-many | Mandatory | Yes | Promotion Name |
| Sales Order | Order Line | one-to-many | Mandatory | Yes | Order Number |
| Sales Order | Payment | one-to-many | Optional | No | Order Number |
| Sales Order | Product Return | one-to-many | Optional | No | Order Number |
| Sales Order | Shipment | one-to-many | Optional | No | Order Number |
| State | City | one-to-many | Mandatory | No | State Name |
| Supplier | Product | one-to-many | Optional | No | Supplier Name |
| Warehouse | Shipment | one-to-many | Optional | No | Warehouse Name |
| Warehouse | Stock Level | one-to-many | Optional | Yes | Warehouse Name |

# Normalization

Actions taken and checks performed while deriving the logical design. Checks that found nothing are listed too, so a compliant design is distinguishable from one that was never examined.

### 1NF — Product Promotion Association

**Resolved many-to-many between Product and Promotion.** A many-to-many relationship cannot be represented without a repeating group. An associative entity keyed on both parents removes the repetition and gives the relationship a place to carry its own attributes later.

### 2NF — Order Line

**Checked non-key attributes against the full composite key.** Order Line has a composite key, so every non-key attribute (Quantity Ordered, Agreed Unit Price) must depend on the whole key rather than part of it. No partial dependency was found.

### 2NF — Order Line

**Identified Order Line as dependent on Sales Order.** Its business key includes Sales Order's key (Order Number), so it cannot be identified independently. The relationship is identifying and the key is propagated rather than duplicated.

### 2NF — Stock Level

**Checked non-key attributes against the full composite key.** Stock Level has a composite key, so every non-key attribute (Quantity On Hand, Reorder Level) must depend on the whole key rather than part of it. No partial dependency was found.

### 2NF — Stock Level

**Identified Stock Level as dependent on Product.** Its business key includes Product's key (Stock Keeping Unit), so it cannot be identified independently. The relationship is identifying and the key is propagated rather than duplicated.

### 2NF — Stock Level

**Identified Stock Level as dependent on Warehouse.** Its business key includes Warehouse's key (Warehouse Name), so it cannot be identified independently. The relationship is identifying and the key is propagated rather than duplicated.

### 3NF — City

**Confirmed State attributes are not repeated on City.** City references State, which references Country. The chain is already decomposed, so Country's attributes reach City by navigation rather than by duplication.

### 3NF — Customer

**Confirmed City attributes are not repeated on Customer.** Customer references City, which references State. The chain is already decomposed, so State's attributes reach Customer by navigation rather than by duplication.

### 3NF — Order Line

**Confirmed Product attributes are not repeated on Order Line.** Order Line references Product, which references Supplier. The chain is already decomposed, so Supplier's attributes reach Order Line by navigation rather than by duplication.

### 3NF — Payment

**Confirmed Sales Order attributes are not repeated on Payment.** Payment references Sales Order, which references Employee. The chain is already decomposed, so Employee's attributes reach Payment by navigation rather than by duplication.

### 3NF — Product Return

**Confirmed Product attributes are not repeated on Product Return.** Product Return references Product, which references Supplier. The chain is already decomposed, so Supplier's attributes reach Product Return by navigation rather than by duplication.

### 3NF — Sales Order

**Confirmed Employee attributes are not repeated on Sales Order.** Sales Order references Employee, which references Department. The chain is already decomposed, so Department's attributes reach Sales Order by navigation rather than by duplication.

### 3NF — Shipment

**Confirmed Warehouse attributes are not repeated on Shipment.** Shipment references Warehouse, which references City. The chain is already decomposed, so City's attributes reach Shipment by navigation rather than by duplication.

### 3NF — Stock Level

**Confirmed Warehouse attributes are not repeated on Stock Level.** Stock Level references Warehouse, which references City. The chain is already decomposed, so City's attributes reach Stock Level by navigation rather than by duplication.

### 3NF — Warehouse

**Confirmed City attributes are not repeated on Warehouse.** Warehouse references City, which references State. The chain is already decomposed, so State's attributes reach Warehouse by navigation rather than by duplication.

# Assumptions

_None identified._
