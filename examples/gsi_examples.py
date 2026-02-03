"""
Global Secondary Index (GSI) Examples

Demonstrates multiple GSIs on a single model with different access patterns.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum

from dynantic import DynamoModel, GSIKey, GSISortKey, Key


class EmployeeStatus(Enum):
    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    TERMINATED = "terminated"


class Employee(DynamoModel):
    """
    Employee model with multiple GSIs:
    - DepartmentIndex: Query by department + hire_date
    - HireDateIndex: Query by hire_date
    - StatusLocationIndex: Query by status + location
    """

    employee_id: str = Key()
    first_name: str
    last_name: str
    email: str

    # GSI 1: Query by department
    department: str = GSIKey(index_name="DepartmentIndex")
    hire_date: date = GSISortKey(index_name="DepartmentIndex") | GSIKey(index_name="HireDateIndex")

    position: str
    salary: Decimal

    # GSI 3: Query by status and location
    status: EmployeeStatus = GSIKey(index_name="StatusLocationIndex")
    location: str = GSISortKey(index_name="StatusLocationIndex")

    manager_id: str | None = None
    skills: set[str] | None = None
    created_at: datetime
    updated_at: datetime

    class Meta:
        table_name = "Employees"


now = datetime.now(timezone.utc)

# Create employees
alice = Employee(
    employee_id="emp-001",
    first_name="Alice",
    last_name="Johnson",
    email="alice@example.com",
    department="Engineering",
    hire_date=date(2020, 3, 15),
    position="Senior Engineer",
    salary=Decimal("120000"),
    status=EmployeeStatus.ACTIVE,
    location="San Francisco",
    skills={"Python", "AWS", "DynamoDB"},
    created_at=now,
    updated_at=now,
)
alice.save()

bob = Employee(
    employee_id="emp-002",
    first_name="Bob",
    last_name="Smith",
    email="bob@example.com",
    department="Engineering",
    hire_date=date(2021, 7, 1),
    position="Software Engineer",
    salary=Decimal("95000"),
    status=EmployeeStatus.ACTIVE,
    location="New York",
    manager_id="emp-001",
    created_at=now,
    updated_at=now,
)
bob.save()

carol = Employee(
    employee_id="emp-003",
    first_name="Carol",
    last_name="Davis",
    email="carol@example.com",
    department="Sales",
    hire_date=date(2019, 1, 10),
    position="Sales Manager",
    salary=Decimal("85000"),
    status=EmployeeStatus.ACTIVE,
    location="Chicago",
    created_at=now,
    updated_at=now,
)
carol.save()

# Get by primary key
employee = Employee.get("emp-001")
if employee:
    print(f"Employee: {employee.first_name} {employee.last_name} - {employee.position}")

# GSI 1: Query by department
engineering = Employee.query_index("DepartmentIndex", "Engineering").all()
print(f"\nEngineering department: {len(engineering)} employees")
for emp in engineering:
    print(f"  - {emp.first_name} {emp.last_name} (hired {emp.hire_date})")

# GSI 1: Query with sort key condition (hired after 2021)
recent_engineers = Employee.query_index("DepartmentIndex", "Engineering").gt(date(2021, 1, 1)).all()
print(f"\nRecent Engineering hires: {len(recent_engineers)}")

# GSI 2: Query by hire date
march_2020_hires = Employee.query_index("HireDateIndex", date(2020, 3, 15)).all()
print(f"\nHired on 2020-03-15: {len(march_2020_hires)}")

# GSI 3: Query by status and location
active_employees = Employee.query_index("StatusLocationIndex", "active").all()
print(f"\nActive employees: {len(active_employees)}")

sf_active = Employee.query_index("StatusLocationIndex", "active").eq("San Francisco").all()
print(f"Active in San Francisco: {len(sf_active)}")

# Atomic update on GSI attribute
Employee.update("emp-002").set(Employee.position, "Senior Engineer").set(
    Employee.salary, Decimal("105000")
).execute()
print("\nPromoted emp-002 to Senior Engineer")

# Pagination with GSI
page = Employee.query_index("DepartmentIndex", "Engineering").limit(1).page()
print(f"\nFirst page: {len(page.items)} items, has_more={page.has_more}")
