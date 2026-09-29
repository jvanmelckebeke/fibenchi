import type { z } from 'zod';
import { companionCalendarSchema } from './generated/calendar.schema.js';
import { companionConfigSchema } from './generated/config.schema.js';
import { indicatorContractSchema } from './generated/indicator.schema.js';

export { companionCalendarSchema, companionConfigSchema, indicatorContractSchema };
export { INDICATOR_CONTRACT } from './generated/indicators.js';

export type CompanionConfig = z.infer<typeof companionConfigSchema>;
export type CompanionCalendar = z.infer<typeof companionCalendarSchema>;
export type IndicatorContract = z.infer<typeof indicatorContractSchema>;
export type IndicatorSpec = IndicatorContract['indicators'][number];
export type Platform = IndicatorSpec['platforms'][number];
