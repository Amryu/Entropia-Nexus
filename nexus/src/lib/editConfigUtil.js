//@ts-nocheck
import { getTierMaterial } from "$lib/tieringUtil";

export const editConfigEffectsOnEquip = {
  constructor: () => ({
    Name: '',
    Values: {
      Strength: null,
    }
  }),
  dependencies: ['effects'],
  controls: [
    { label: 'Name', type: 'select', options: (_, d) => d.effects.map(x => x.Name), '_get': x => x.Name, '_set': (x, v) => x.Name = v},
    { label: 'Strength', type: 'number', step: '0.1', min: '0', '_get': x => x.Values?.Strength, '_set': (x, v) => x.Values.Strength = v},
  ]
};

export const editConfigEffectsOnSetEquip = {
  constructor: () => ({
    Name: '',
    Values: {
      Strength: null,
      MinSetPieces: null,
    }
  }),
  dependencies: ['effects'],
  sort: (a, b) => (a.Values.MinSetPieces - b.Values.MinSetPieces) || a.Name.localeCompare(b.Name),
  controls: [
    { label: 'Name', type: 'select', options: (_, d) => d.effects.map(x => x.Name), '_get': x => x.Name, '_set': (x, v) => x.Name = v},
    { label: 'Strength', type: 'number', step: '0.1', '_get': x => x.Values?.Strength, '_set': (x, v) => x.Values.Strength = v},
    { label: 'Piece Count', type: 'number', step: '1', min: '1', max: '7', '_get': x => x.Values?.MinSetPieces, '_set': (x, v) => x.Values.MinSetPieces = v},
  ]
};

export const editConfigEffectsOnUse = {
  constructor: () => ({
    Name: '',
    Values: {
      Strength: null,
      DurationSeconds: null,
    }
  }),
  controls: [
    { label: 'Name', type: 'select', options: (_, d) => d.effects.map(x => x.Name), '_get': x => x.Name, '_set': (x, v) => x.Name = v},
    { label: 'Strength', type: 'number', step: '0.1', '_get': x => x.Values?.Strength, '_set': (x, v) => x.Values.Strength = v},
    { label: 'Duration (s)', type: 'number', step: '0.1', min: '0', '_get': x => x.Values?.DurationSeconds, '_set': (x, v) => x.Values.DurationSeconds = v},
  ]
};

export function getEditConfigTier(type) {
  return {
    constructor: i => {
      return {
        Properties: {
          Tier: i + 1,
        },
        Materials: new Array(5).fill(null).map((_, j) => ({ Material: { Name: getTierMaterial(type, i + 1, j) }, Amount: 0 })),
      };
    },
    controls: [
      { label: x => getTierMaterial(type, x.Properties.Tier, 0), type: 'number', step: '1', min: '0', '_get': x => x.Materials[0].Amount, '_set': (x, v) => x.Materials[0].Amount = v},
      { label: x => getTierMaterial(type, x.Properties.Tier, 1), type: 'number', step: '1', min: '0', '_get': x => x.Materials[1].Amount, '_set': (x, v) => x.Materials[1].Amount = v},
      { label: x => getTierMaterial(type, x.Properties.Tier, 2), type: 'number', step: '1', min: '0', '_get': x => x.Materials[2].Amount, '_set': (x, v) => x.Materials[2].Amount = v},
      { label: x => getTierMaterial(type, x.Properties.Tier, 3), type: 'number', step: '1', min: '0', '_get': x => x.Materials[3].Amount, '_set': (x, v) => x.Materials[3].Amount = v},
      { label: x => getTierMaterial(type, x.Properties.Tier, 4), type: 'number', step: '1', min: '0', '_get': x => x.Materials[4].Amount, '_set': (x, v) => x.Materials[4].Amount = v},
    ]
  };
}