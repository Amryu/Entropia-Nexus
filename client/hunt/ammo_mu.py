"""Ammo types that carry markup.

Only a handful of ammo types have MU above TT in the player economy:
Explosive Projectiles for projectile weapons, Mind Essence / Light Mind
Essence for laser weapons, and Decoys as a combat utility. All other
ammo is MU neutral (buys at 101%, sells at 101%).
"""

AMMO_MU_TYPES: tuple[str, ...] = (
    "Explosive Projectiles",
    "Mind Essence",
    "Light Mind Essence",
    "Decoy",
)

AMMO_MU_TYPES_LOWER: frozenset[str] = frozenset(name.lower() for name in AMMO_MU_TYPES)


def is_mu_ammo(name: str | None) -> bool:
    if not name:
        return False
    return name.lower() in AMMO_MU_TYPES_LOWER
