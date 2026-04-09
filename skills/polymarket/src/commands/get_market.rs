use anyhow::Result;
use reqwest::Client;

use crate::api::{get_clob_market, get_gamma_market_by_slug, get_orderbook};
use crate::sanitize::{sanitize_opt, sanitize_opt_owned, sanitize_str};

pub async fn run(market_id: &str) -> Result<()> {
    let client = Client::new();

    // Determine if market_id is a condition_id (0x-prefixed hex) or a slug
    let output = if market_id.starts_with("0x") || market_id.starts_with("0X") {
        run_by_condition_id(&client, market_id).await?
    } else {
        run_by_slug(&client, market_id).await?
    };

    println!("{}", serde_json::to_string_pretty(&output)?);
    Ok(())
}

async fn run_by_condition_id(client: &Client, condition_id: &str) -> anyhow::Result<serde_json::Value> {
    let market = get_clob_market(client, condition_id).await?;

    let yes_token = market.tokens.iter().find(|t| t.outcome.to_lowercase() == "yes");
    let no_token = market.tokens.iter().find(|t| t.outcome.to_lowercase() == "no");

    let mut yes_book = None;

    if let Some(yes) = yes_token {
        if let Ok(book) = get_orderbook(client, &yes.token_id).await {
            yes_book = Some(book);
        }
    }
    // Enrich with NO book if needed in future; currently unused
    if let Some(no) = no_token {
        let _ = get_orderbook(client, &no.token_id).await.ok();
    }

    let yes_best_bid = yes_book
        .as_ref()
        .and_then(|b| b.bids.first())
        .map(|l| l.price.clone());
    let yes_best_ask = yes_book
        .as_ref()
        .and_then(|b| b.asks.first())
        .map(|l| l.price.clone());
    let yes_last = yes_book
        .as_ref()
        .and_then(|b| b.last_trade_price.clone());

    Ok(serde_json::json!({
        "ok": true,
        "data": {
            "condition_id": market.condition_id,
            "question": sanitize_opt(market.question.as_deref()),
            "active": market.active,
            "closed": market.closed,
            "accepting_orders": market.accepting_orders,
            "neg_risk": market.neg_risk,
            "end_date": market.end_date_iso,
            "tokens": market.tokens.iter().map(|t| serde_json::json!({
                "outcome": sanitize_str(&t.outcome),
                "token_id": t.token_id,
                "price": t.price,
                "winner": t.winner,
            })).collect::<Vec<_>>(),
            "yes_best_bid": yes_best_bid,
            "yes_best_ask": yes_best_ask,
            "yes_last_trade": yes_last,
        }
    }))
}

async fn run_by_slug(client: &Client, slug: &str) -> anyhow::Result<serde_json::Value> {
    let market = get_gamma_market_by_slug(client, slug).await?;
    let token_ids = market.token_ids();
    let prices = market.prices();
    let outcomes = market.outcome_list();

    let yes_token_id = token_ids.first().cloned().unwrap_or_default();
    let no_token_id = token_ids.get(1).cloned().unwrap_or_default();

    // Try to enrich with live order book data
    let yes_book = if !yes_token_id.is_empty() {
        get_orderbook(client, &yes_token_id).await.ok()
    } else {
        None
    };
    let _no_book = if !no_token_id.is_empty() {
        get_orderbook(client, &no_token_id).await.ok()
    } else {
        None
    };

    let yes_best_bid = yes_book.as_ref().and_then(|b| b.bids.first()).map(|l| l.price.clone());
    let yes_best_ask = yes_book.as_ref().and_then(|b| b.asks.first()).map(|l| l.price.clone());
    let yes_last = yes_book.as_ref().and_then(|b| b.last_trade_price.clone());

    let token_info: Vec<serde_json::Value> = outcomes.iter().enumerate().map(|(i, outcome)| {
        serde_json::json!({
            "outcome": sanitize_str(outcome),
            "token_id": token_ids.get(i).cloned().unwrap_or_default(),
            "price": prices.get(i).cloned().unwrap_or_default(),
        })
    }).collect();

    Ok(serde_json::json!({
        "ok": true,
        "data": {
            "id": market.id,
            "condition_id": market.condition_id,
            "slug": sanitize_opt_owned(&market.slug),
            "question": sanitize_opt_owned(&market.question),
            "description": sanitize_opt_owned(&market.description),
            "category": sanitize_opt_owned(&market.category),
            "end_date": market.end_date,
            "active": market.active,
            "closed": market.closed,
            "accepting_orders": market.accepting_orders,
            "neg_risk": market.neg_risk,
            "fee": market.fee,
            "tokens": token_info,
            "volume_24hr": market.volume24hr,
            "volume": market.volume,
            "liquidity": market.liquidity,
            "best_bid": market.best_bid,
            "best_ask": market.best_ask,
            "last_trade_price": market.last_trade_price,
            "yes_best_bid": yes_best_bid,
            "yes_best_ask": yes_best_ask,
            "yes_last_trade": yes_last,
        }
    }))
}
