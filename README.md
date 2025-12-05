# Steam Achievements Export  
Steam Achievements Export は、Steam アカウントが所有しているゲームの実績情報を  
**日本語でわかりやすく CSV に一括出力できる Windows アプリ**です。

Steam API を利用して  
- ゲームタイトル  
- 実績名  
- 実績説明  
- 取得状況（✓ / ✗）  

などを取得し、Excel や Google スプレッドシートで分析しやすい形式で書き出せます。

---

## 🌍 Languages / 言語
[🇺🇸 English](#english-version) | [🇯🇵 日本語](#日本語版)

---

# 🇯🇵 日本語版
## **Steam Achievements Export とは？**  
Steam で所有しているゲームの実績情報を一括取得し、  
日本語でわかりやすく CSV に書き出せる Windows 専用アプリです。  

Steam API を利用して、  
ゲームタイトル / 実績名 / 実績説明 / 取得状況（✓ / ✗）  
をまとめて取得し、  
Excel や Google スプレッドシートで分析・整理できる形式で出力します。  
<br><br>

## 🔹 日本語タイトル・日本語実績に対応  
対応しているゲームは、ゲーム名も実績名も日本語で取得できます。  
<br>

## 🔹 所有ゲームを自動取得  
API Key と SteamID64 を入力するだけで、  
Steam アカウントが所有するすべてのゲームを一覧化します。  
<br>

## 🔹 ゲーム検索・フィルタリング  
上部の検索バーから  
ゲーム一覧をリアルタイムに検索できます。  
<br>

## 🔹 チェックしたゲームだけ書き出し  
「Select All」「Clear」に加えて、  
必要なゲームのみ CSV に出力できます。  
<br><br>


# **使用方法**  
⓵ exe を起動し、設定ページを開きます。  

⓶ Steam Web API Key を取得  
1. https://steamcommunity.com/dev/apikey  
2. Steam アカウントでログイン  
3. Domain に `localhost` と入力  
4. 「Register」で API Key が発行されます  

⓷ SteamID64 を確認  
1. 自分の Steam プロフィールを開く  
2. https://steamid.io/ にプロフィール URL を貼る  
3. 表示される **SteamID64（17桁）** を使用  

⓸ 出力先 CSV に保存したいフォルダを指定  

⓹ 実績タブで所持ゲーム一覧が表示されます  

⓺ チェックしたゲームを選び、**Export** を押すと CSV が生成されます  
<br>

## 📝 注意事項  
- 実績データは Steam API / ゲーム側が公開している範囲で取得されます  
- 一部ゲームは実績情報が非公開  
- 所持ゲームのみ取得可能（ファミリーシェアリングは不可）  
- Steam API Key は無料で取得できます  

---

# 🇺🇸 English Version
## **What is Steam Achievements Export?**  
Steam Achievements Export is a Windows application that allows you to  
**retrieve all achievement data for your owned Steam games and export them to a CSV file**,  
with full support for Japanese translation where available.

Using the Steam Web API, the app collects:
- Game title  
- Achievement name  
- Achievement description  
- Unlock status (✓ / ✗)  

You can then open the CSV in Excel or Google Sheets for organization and analysis.  
<br><br>

## 🔹 Supports Japanese Game Titles & Achievements  
For supported games, both the game name and achievement names/descriptions are retrieved in Japanese.  
<br>

## 🔹 Automatically Retrieves Owned Games  
Simply enter your API Key and SteamID64—  
the app will list all games owned by your Steam account.  
<br>

## 🔹 Search & Filter Games  
Use the search bar to filter your game list in real time.  
<br>

## 🔹 Export Only the Selected Games  
You can export achievements for only the games you selected,  
using features like **Select All** and **Clear**.  
<br><br>

# **How to Use**
1. Launch the executable and open the **Settings** page.  

2. Get your Steam Web API Key  
   1. Visit https://steamcommunity.com/dev/apikey  
   2. Log in with your Steam account  
   3. Enter `localhost` as the Domain  
   4. Click **Register** to obtain your API Key  

3. Find your SteamID64  
   1. Open your Steam profile page  
   2. Go to https://steamid.io/ and paste your profile URL  
   3. Use the displayed **SteamID64 (17 digits)**  

4. Choose the output folder for the CSV file  

5. Open the **Achievements** tab to view your owned games  

6. Select the games you want to export and click **Export**  
<br>

## 📝 Notes
- Achievement data availability depends on Steam API and each game  
- Some games do not expose achievement details  
- Only achievements for games you personally own can be retrieved  
- Steam API Key is free to obtain  

---
