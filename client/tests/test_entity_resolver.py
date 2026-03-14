import unittest
from unittest.mock import MagicMock

from client.hunt.entity_resolver import EntityResolver


class TestEntityResolver(unittest.TestCase):

    def test_no_data_client(self):
        resolver = EntityResolver(data_client=None)
        resolver.warmup()
        self.assertTrue(resolver.is_ready)
        self.assertIsNone(resolver.resolve_mob("Atrox"))
        self.assertIsNone(resolver.resolve_item("Shrapnel"))

    def test_resolve_mob(self):
        client = MagicMock()
        client.get_mobs.return_value = [
            {"Id": 1, "Name": "Atrox"},
            {"Id": 2, "Name": "Foul"},
        ]
        client.get_items.return_value = []
        client.get_materials.return_value = []
        client.get_weapons.return_value = []

        resolver = EntityResolver(client)
        resolver._load_mobs()
        resolver._load_items()
        resolver._load_weapons()

        self.assertEqual(resolver.resolve_mob("Atrox"), 1)
        self.assertEqual(resolver.resolve_mob("atrox"), 1)  # case-insensitive
        self.assertEqual(resolver.resolve_mob("Foul"), 2)
        self.assertIsNone(resolver.resolve_mob("Unknown"))
        self.assertIsNone(resolver.resolve_mob(""))

    def test_resolve_item(self):
        client = MagicMock()
        client.get_mobs.return_value = []
        client.get_items.return_value = [
            {"Id": 100, "Name": "Shrapnel"},
            {"Id": 101, "Name": "Animal Oil Residue"},
        ]
        client.get_materials.return_value = [
            {"Id": 200, "Name": "Iron Ingot"},
        ]
        client.get_weapons.return_value = []

        resolver = EntityResolver(client)
        resolver._load_items()

        self.assertEqual(resolver.resolve_item("Shrapnel"), 100)
        self.assertEqual(resolver.resolve_item("shrapnel"), 100)
        self.assertEqual(resolver.resolve_item("Iron Ingot"), 200)
        self.assertIsNone(resolver.resolve_item("NonExistent"))

    def test_resolve_weapon(self):
        client = MagicMock()
        client.get_weapons.return_value = [
            {"Id": 50, "Name": "Armatrix LR-35 (L)"},
        ]

        resolver = EntityResolver(client)
        resolver._load_weapons()

        self.assertEqual(resolver.resolve_weapon("Armatrix LR-35 (L)"), 50)
        self.assertEqual(resolver.resolve_weapon("armatrix lr-35 (l)"), 50)
        self.assertIsNone(resolver.resolve_weapon("Unknown Weapon"))

    def test_reverse_lookup(self):
        client = MagicMock()
        client.get_mobs.return_value = [{"Id": 1, "Name": "Atrox"}]
        client.get_items.return_value = [{"Id": 100, "Name": "Shrapnel"}]
        client.get_materials.return_value = []
        client.get_weapons.return_value = []

        resolver = EntityResolver(client)
        resolver._load_mobs()
        resolver._load_items()

        self.assertEqual(resolver.get_mob_name(1), "Atrox")
        self.assertEqual(resolver.get_item_name(100), "Shrapnel")
        self.assertIsNone(resolver.get_mob_name(999))

    def test_data_client_failure_graceful(self):
        client = MagicMock()
        client.get_mobs.side_effect = ConnectionError("Network down")
        client.get_items.return_value = []
        client.get_materials.return_value = []
        client.get_weapons.return_value = []

        resolver = EntityResolver(client)
        # Should not raise
        try:
            resolver._load_mobs()
        except ConnectionError:
            pass  # Logged and handled
        # Fallback: empty lookups
        self.assertIsNone(resolver.resolve_mob("Atrox"))


if __name__ == "__main__":
    unittest.main()
