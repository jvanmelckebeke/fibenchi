import type { z } from 'zod';
import { companionCalendarSchema } from './generated/calendar.schema.js';
import { companionConfigSchema } from './generated/config.schema.js';

export { companionCalendarSchema, companionConfigSchema };
export {
  INDICATOR_CONTRACT,
  type IndicatorContract,
  type IndicatorSpec,
  type Platform,
} from './generated/indicators.js';

export type CompanionConfig = z.infer<typeof companionConfigSchema>;
export type CompanionCalendar = z.infer<typeof companionCalendarSchema>;
