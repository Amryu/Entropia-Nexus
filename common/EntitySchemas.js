import { Absorber } from "./schemas/Absorber.js";
import { Apartment } from "./schemas/Apartment.js";
import { ArmorPlating } from "./schemas/ArmorPlating.js";
import { ArmorSet } from "./schemas/ArmorSet.js";
import { Area } from "./schemas/Area.js";
import { Blueprint } from "./schemas/Blueprint.js";
import { Capsule } from "./schemas/Capsule.js";
import { Clothing } from "./schemas/Clothing.js";
import { Consumable } from "./schemas/Consumable.js";
import { Decoration } from "./schemas/Decoration.js";
import { EffectChip } from "./schemas/EffectChip.js";
import { Excavator } from "./schemas/Excavator.js";
import { Finder } from "./schemas/Finder.js";
import { FinderAmplifier } from "./schemas/FinderAmplifier.js";
import { Furniture } from "./schemas/Furniture.js";
import { Location } from "./schemas/Location.js";
import { Material } from "./schemas/Material.js";
import { MedicalChip } from "./schemas/MedicalChip.js";
import { MedicalTool } from "./schemas/MedicalTool.js";
import { MindforceImplant } from "./schemas/MindforceImplant.js";
import { MiscTool } from "./schemas/MiscTool.js";
import { Mob } from "./schemas/Mob.js";
import { Mission } from "./schemas/Mission.js";
import { Pet } from "./schemas/Pet.js";
import { Profession } from "./schemas/Profession.js";
import { Refiner } from "./schemas/Refiner.js";
import { Scanner } from "./schemas/Scanner.js";
import { Skill } from "./schemas/Skill.js";
import { Sign } from "./schemas/Sign.js";
import { StorageContainer } from "./schemas/StorageContainer.js";
import { Strongbox } from "./schemas/Strongbox.js";
import { TeleportationChip } from "./schemas/TeleportationChip.js";
import { Vehicle } from "./schemas/Vehicle.js";
import { Vendor } from "./schemas/Vendor.js";
import { Weapon } from "./schemas/Weapon.js";
import { WeaponAmplifier } from "./schemas/WeaponAmplifier.js";
import { WeaponVisionAttachment } from "./schemas/WeaponVisionAttachment.js";
import { Shop } from "./schemas/Shop.js";

export const EntitySchemas = {
  Absorber,
  Apartment,
  ArmorPlating,
  ArmorSet,
  Area,
  Blueprint,
  Capsule,
  Clothing,
  Consumable,
  Decoration,
  EffectChip,
  Excavator,
  Finder,
  FinderAmplifier,
  Furniture,
  Location,
  Material,
  MedicalChip,
  MedicalTool,
  MindforceImplant,
  MiscTool,
  Mob,
  Mission,
  Pet,
  Profession,
  Refiner,
  Scanner,
  Skill,
  Sign,
  StorageContainer,
  Strongbox,
  TeleportationChip,
  Vehicle,
  Vendor,
  Weapon,
  WeaponAmplifier,
  WeaponVisionAttachment,
  Shop,
  get TeleportChip() { return this.TeleportationChip; },
  get CreatureControlCapsule() { return this.Capsule; }
}
