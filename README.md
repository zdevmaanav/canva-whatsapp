# Canva → WhatsApp Bulk Tool

## What this tool is

#Purpose:# Takes images (from a local folder or links in a Google Sheet), drops them into a fixed Canva template, and sends the finished designs to WhatsApp numbers — in bulk, for up to ~100 people. Built to be reused across different clients, each with their own accounts.

## The flow:
Google Sheet (image + number)  +  local images
                ↓
        [1] Tool builds a data file
                ↓
        [2] Canva fills the template (automated browser, manual fallback)
                ↓
        [3] Tool splits the result, sends each to its number via Gupshup
