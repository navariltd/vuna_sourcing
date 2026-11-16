export type DynamicFieldType =
  | "Short Text"
  | "Long Text"
  | "Whole Number"
  | "Number"
  | "Date"
  | "Yes / No"
  | "Multiple Choice";

export type DynamicFieldValue = string | number | null;

export interface DynamicFieldDefinition {
  label: string;
  field_type: DynamicFieldType;
  mandatory: boolean;
  description: string | null;
  choices: string[];
}

export const RADIO_LIMIT = 5;

export const TEXT_LIMITS: Partial<Record<DynamicFieldType, number>> = {
  "Short Text": 140,
  "Long Text": 2000,
};

export function isBlankValue(value: DynamicFieldValue | undefined) {
  return value === null || value === undefined || String(value).trim() === "";
}
