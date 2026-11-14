import config


def llm_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = config.PRICES_PER_MTOK.get(model, (0.0, 0.0))
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000
