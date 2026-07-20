# ICSA -- Authentication & Database Stabilization Roadmap

**Objective:** Stabilize the database architecture, improve
authentication security, and prepare the project for future production
deployment before continuing with the remaining PRD modules.

------------------------------------------------------------------------

# Phase 1 -- Database Architecture Stabilization (Critical)

## Step 1.1 -- Introduce Environment-Based Database Configuration

### Objective

Create a centralized database configuration that supports multiple
environments without modifying application logic.

### Target Environments

-   Development
-   UAT
-   Testing
-   Production (Future)

### Deliverable

-   Single configuration source responsible for selecting the active
    database.

------------------------------------------------------------------------

## Step 1.2 -- Separate Database Files

### Objective

Ensure each environment has its own isolated database.

### Recommended Structure

``` text
data/
    saas.db          ← Development
    uat_saas.db      ← UAT
    test.db          ← Automated Tests
```

### Expected Result

-   Test scripts must never modify the development database.
-   Development work remains persistent regardless of testing
    activities.

------------------------------------------------------------------------

## Step 1.3 -- Stop Tracking Runtime Databases

### Objective

Prevent Git from resetting development data.

### Tasks

-   Remove runtime databases from version control.
-   Add database patterns to `.gitignore`.

### Expected Result

Runtime data persists independently of Git operations.

------------------------------------------------------------------------

## Step 1.4 -- Protect Destructive Operations

### Objective

Prevent accidental deletion of development data.

### Requirements

Any script that performs: - `drop_all()` - `create_all()` -
`os.remove()` - Database reset operations

must verify that it is operating only on the intended UAT or test
database.

### Expected Result

Development data can never be wiped accidentally.

------------------------------------------------------------------------

# Phase 2 -- Authentication Redesign

## Step 2.1 -- Remove Administrator Registration

### Objective

Eliminate public creation of administrator accounts.

### Requirements

The registration page must only allow: - Customer - Restaurant Owner

Administrator must not appear as a selectable role.

### Expected Result

Administrator accounts cannot be created through the UI.

------------------------------------------------------------------------

## Step 2.2 -- Seed Administrator Account

### Objective

Create a permanent administrator account during database initialization.

### Requirements

-   Store credentials in the database.
-   Store the password as a bcrypt hash.
-   Never store plain-text passwords.
-   The account should behave like any other authenticated user.

### Expected Result

A permanent administrator account always exists.

------------------------------------------------------------------------

## Step 2.3 -- Automatic Administrator Creation

### Objective

Create the administrator account only if it does not already exist.

### Logic

``` text
If administrator exists:
    Do nothing

Else:
    Create administrator account
```

### Expected Result

Idempotent initialization with no duplicate administrator accounts.

------------------------------------------------------------------------

## Step 2.4 -- Unified Login System

### Objective

Use a single login page for every user.

### Flow

``` text
Customer
Restaurant Owner
Administrator
        ↓
Common Login Page
        ↓
Authentication
        ↓
Role-Based Routing
```

### Expected Result

No separate administrator login page is required.

------------------------------------------------------------------------

## Step 2.5 -- Automatic Role-Based Dashboard Routing

### Objective

Automatically redirect users based on their authenticated role.

### Routing

``` text
Customer
    ↓
Customer Dashboard

Restaurant Owner
    ↓
Restaurant Dashboard

Administrator
    ↓
Admin Dashboard
```

### Expected Result

Dashboard selection becomes automatic.

------------------------------------------------------------------------

# Phase 3 -- Security Hardening

## Step 3.1 -- Protect Administrator Routes

Every administrator page must verify:

``` python
current_user.role == ADMIN
```

before rendering.

------------------------------------------------------------------------

## Step 3.2 -- Hide Administrator Features

Customers and restaurant owners must never see:

-   Admin Dashboard
-   User Management
-   Tenant Management
-   Global Analytics
-   System Settings
-   Audit Logs

------------------------------------------------------------------------

## Step 3.3 -- Prevent Privilege Escalation

Users must never be able to: - Change their own role - Modify session
state to become an administrator - Modify JWT payloads to gain
privileges

Authorization must always be enforced server-side.

------------------------------------------------------------------------

# Phase 4 -- Developer Experience Improvements

## Step 4.1 -- Dedicated Seed Script

Create a reusable seed process that inserts demo data only when missing.

### Seed Data

-   Administrator
-   Demo Restaurant
-   Demo Restaurant Manager
-   Demo Customer

------------------------------------------------------------------------

## Step 4.2 -- Safe Reset Utility

Reset operations must target only:

``` text
data/test.db
```

or

``` text
data/uat_saas.db
```

Never:

``` text
data/saas.db
```

unless explicitly requested.

------------------------------------------------------------------------

# Phase 5 -- Verification

The implementation is complete only after the following checks succeed.

## Database Verification

-   Development database survives normal application restart.
-   UAT scripts no longer modify the development database.
-   Environment selection is functioning correctly.

## Authentication Verification

-   Administrator cannot register through the UI.
-   Seeded administrator can log in successfully.
-   Customer registration works.
-   Restaurant Owner registration works.

## Routing Verification

-   Customers reach the Customer Dashboard.
-   Restaurant Owners reach the Restaurant Dashboard.
-   Administrators reach the Admin Dashboard.

## Security Verification

-   Administrator pages reject non-admin users.
-   Privilege escalation attempts fail.
-   Hidden administrator functionality remains inaccessible to non-admin
    users.

------------------------------------------------------------------------

# Recommended Implementation Order

    Order Task                                         Priority
  ------- -------------------------------------------- -------------
        1 Environment-Based Database Configuration     🔴 Critical
        2 Separate Development, UAT & Test Databases   🔴 Critical
        3 Remove Runtime Database from Git             🔴 Critical
        4 Protect Destructive Database Operations      🔴 Critical
        5 Remove Administrator Registration            🟠 High
        6 Seed Permanent Administrator Account         🟠 High
        7 Automatic Administrator Creation             🟠 High
        8 Unified Login & Role-Based Routing           🟠 High
        9 Secure Administrator Routes & RBAC           🟡 Medium
       10 Seed & Reset Utilities                       🟡 Medium
       11 End-to-End Verification                      🟡 Medium

------------------------------------------------------------------------

# Expected Outcome

After completing this roadmap, the project will have:

-   Stable environment-aware database architecture.
-   Persistent development data.
-   Isolated UAT and testing environments.
-   Secure administrator provisioning.
-   Unified authentication with automatic role-based routing.
-   Stronger RBAC and privilege protection.
-   A production-oriented authentication and database foundation for
    future PRD implementation.
