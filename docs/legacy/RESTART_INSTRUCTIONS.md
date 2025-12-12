# Force Server Restart Instructions

## The Problem
Changes to `main_graph.py` aren't taking effect. Uvicorn's auto-reload isn't reloading the graph module properly.

## Solution
**Complete restart procedure:**

1. **Stop uvicorn completely** (Ctrl+C)
2. **Clear Python cache**:
   ```powershell
   python clear_cache.py
   ```
3. **Restart uvicorn**:
   ```powershell
   uvicorn main:app --reload --env-file .env --log-level debug
   ```
4. **Wait for "Application startup complete"**
5. **Send ONE WhatsApp message**: "search for lipstick"

## What You Should See

If the fix is working, you'll see these logs IN ORDER:

```
====================================================================================================
>>> WEBHOOK FUNCTION CALLED - NEW CODE VERSION <<<
====================================================================================================

>>> ABOUT TO INVOKE GRAPH <<<

>>> SALES AGENT: Invoking LLM for +234xxx
>>> SALES AGENT: Conversation has 2 messages

>>> SALES AGENT: LLM Response received
>>> SALES AGENT: Response type: AIMessage
>>> SALES AGENT: Response content: 'EMPTY/NONE'
>>> SALES AGENT: Has tool_calls: True
>>> SALES AGENT: Tool calls: ['search_products_tool']

>>> ROUTING: Sales agent requested tools, going to tool_execution

>>> TOOL: search_products called with query='lipstick'
>>> TOOL: search_products got results: ...

>>> SALES AGENT: Invoking LLM for +234xxx (2nd time with tool results)
>>> SALES AGENT: Response content: 'We have Red Matte Lipstick...'
>>> SALES AGENT: Has tool_calls: False

>>> ROUTING: No tools needed, proceeding to cache_update

>>> GRAPH COMPLETED <<<
>>> Messages in final_state: 5 or more
>>>   [0] HumanMessage - search for lipstick
>>>   [1] AIMessage - EMPTY (tool call)
>>>   [2] ToolMessage - product results
>>>   [3] AIMessage - We have Red Matte Lipstick (₦3500)...
```

## If You Still Don't See These Logs

The graph module cache might be stuck. Try:
```powershell
Remove-Item -Recurse -Force app\__pycache__ -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force app\graphs\__pycache__ -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force app\agents\__pycache__ -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force app\tools\__pycache__ -ErrorAction SilentlyContinue
```

Then restart uvicorn again.
