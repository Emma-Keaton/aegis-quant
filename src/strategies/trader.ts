import { getStrategy } from './index';
import type { StrategyConfig } from './index';

export interface TraderState {
  company_of_interest: string;
  investment_plan: string;
  strategy?: string;
  market_regime?: string;
}

export interface TradeProposal {
  recommendation: 'BUY' | 'SELL' | 'HOLD';
  reasoning: string;
  strategy?: string;
}

/**
 * Creates a trader instance bound to the supplied language model.
 * Uses the YAML strategy playbooks from src/strategies to shape the
 * proposal. Real deployments should invoke an LLM via HTTP API; this
 * implementation applies the matched strategy's scoring guidance.
 */
export function createTrader(_: unknown) {
  return {
    run(state: TraderState): TradeProposal {
      const strategy: StrategyConfig | undefined = state.strategy
        ? getStrategy(state.strategy)
        : undefined;

      const investmentPlan = state.investment_plan.toLowerCase();
      const planSell = investmentPlan.includes('sell');
      const planBuy = investmentPlan.includes('buy') || investmentPlan.includes('买入');

      let recommendation: TradeProposal['recommendation'] = 'HOLD';
      if (planSell) recommendation = 'SELL';
      else if (planBuy || strategy) recommendation = 'BUY';

      const prefix = strategy
        ? `Strategy "${strategy.display_name}" (${strategy.name}) applies: ${strategy.description}`
        : `Based on the investment plan for ${state.company_of_interest}`;

      const guidance = strategy
        ? ` Requires ${strategy.required_tools.join(', ')}; rules ${strategy.core_rules.join(', ')}.`
        : '';

      return {
        recommendation,
        reasoning: `${prefix}.${guidance} Agent recommends ${recommendation}.`,
        strategy: strategy?.name,
      };
    },
  };
}
