from datetime import datetime, timedelta
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def generate_expires_at(seconds: int = 300) -> datetime:
    return datetime.utcnow() + timedelta(seconds=seconds)


def parse_dimensions(text: str) -> list[str]:
    """'2*3, 3.5*4' → ['2*3', '3.5*4']"""
    return [d.strip() for d in text.replace(";", ",").split(",") if d.strip()]


def calculate_area(dims: list[str]) -> int:
    """['2*3', '3.5*4'] → 20 (int ga aylantiradi)"""
    total = 0.0
    for dim in dims:
        try:
            parts = dim.strip().split("*")
            if len(parts) == 2:
                total += float(parts[0]) * float(parts[1])
        except ValueError:
            continue
    return int(total)


def is_valid_dimensions(text: str) -> bool:
    dims = parse_dimensions(text)
    if not dims:
        return False
    for dim in dims:
        parts = dim.split("*")
        if len(parts) != 2:
            return False
        try:
            a, b = float(parts[0]), float(parts[1])
            if a <= 0 or b <= 0:
                return False
        except ValueError:
            return False
    return True


def calculate_discount(total_area_m2: int) -> float:
    """
    Chegirma foizi:
    < 20m²   → 0%
    20-40m²  → 6%
    40-70m²  → 12%
    70-100m² → 18%
    100+m²   → 25%
    """
    if total_area_m2 < 20:
        return 0.0
    elif total_area_m2 < 40:
        return 6.0
    elif total_area_m2 < 70:
        return 12.0
    elif total_area_m2 < 100:
        return 18.0
    else:
        return 25.0


def apply_discount(amount: float, discount_percent: float) -> float:
    """Chegirmadan keyin narx"""
    return amount * (1 - discount_percent / 100)


def should_add_debt(total_amount: float, paid_amount: float) -> bool:
    """
    10,000 so'mdan kam farq bo'lsa qarzga yozilmaydi
    """
    return (total_amount - paid_amount) >= 10_000


def fmt_money(amount: float) -> str:
    return f"{int(amount):,} so'm".replace(",", " ")


def fmt_area(area: int) -> str:
    return f"{area} m²"