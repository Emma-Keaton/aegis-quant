import { load } from 'js-yaml';

export interface StrategyConfig {
  name: string;
  display_name: string;
  description: string;
  category: string;
  core_rules: number[];
  required_tools: string[];
  aliases: string[];
  default_active: boolean;
  default_router: boolean;
  default_priority: number;
  market_regimes: string[];
  instructions: string;
}

const modules = import.meta.glob('./*.yaml', {
  eager: true,
  query: '?raw',
  import: 'default',
}) as Record<string, string>;

const parsed: StrategyConfig[] = Object.entries(modules)
  .map(([file, raw]) => {
    try {
      const cfg = load(raw) as StrategyConfig;
      return {
        ...cfg,
        core_rules: cfg.core_rules ?? [],
        required_tools: cfg.required_tools ?? [],
        aliases: cfg.aliases ?? [],
        market_regimes: cfg.market_regimes ?? [],
        default_priority: cfg.default_priority ?? 99,
      };
    } catch (err) {
      console.error(`[strategies] failed to parse ${file}:`, err);
      return null;
    }
  })
  .filter((s): s is StrategyConfig => s !== null)
  .sort((a, b) => a.default_priority - b.default_priority);

export function getStrategies(): StrategyConfig[] {
  return parsed;
}

export function getStrategy(name: string): StrategyConfig | undefined {
  return parsed.find(
    (s) => s.name === name || (s.aliases ?? []).includes(name),
  );
}

export function getActiveStrategies(): StrategyConfig[] {
  return parsed.filter((s) => s.default_active);
}

export function getDefaultRouterStrategy(): StrategyConfig | undefined {
  return parsed.find((s) => s.default_router);
}
