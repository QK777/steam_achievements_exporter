# Steam Achievements Export  

## 🌍 Languages / 言語
[🇺🇸 English](#english-version) | [🇯🇵 日本語](#japanese-version)

---

# <a id="japanese-version"></a>🇯🇵 日本語版  

## Steam Achievements Export とは？  
Steam Achievements Export は、Steam アカウントが所有しているゲームの実績情報を  
**わかりやすく CSV に一括出力できる Windows アプリ**です。

Steam API を利用して  
- ゲームタイトル  
- 実績名  
- 実績説明  
- 取得状況（✓ / ✗）  

を取得し、Excel や Google スプレッドシートで分析しやすい形式で書き出せます。  
**実績をスプレッドシートで管理したい方に向けたアプリです。**

<br>

## 🔹 日本語タイトル・日本語実績に対応  
対応しているゲームは、ゲーム名も実績名も日本語で取得できます。  

## 🔹 所有ゲームを自動取得  
API Key と SteamID64 を入力、Steamフォルダの指定をすることで
Steam アカウントが所有するすべてのゲームを一覧化します。  

## 🔹 ゲーム検索・フィルタリング  
検索バーからリアルタイムにゲーム一覧を絞り込みできます。  

## 🔹 チェックしたゲームだけ書き出し  
「Select All」「Clear」機能を搭載し、  
必要なゲームだけを CSV に出力できます。  

<br>

# 📘 使用方法  

### ① exe を起動し、設定ページを開く  

### ② Steam Web API Key を取得する  
1. https://steamcommunity.com/dev/apikey にアクセス  
2. Steam アカウントでログイン  
3. Domain に `localhost` と入力  
4. 「Register」→ API Key が発行される  

### ③ SteamID64 を確認する  
1. 自分の Steam プロフィールを開く  
2. https://steamid.io/ にプロフィール URL を貼る  
3. 表示された **SteamID64（17桁）** を使用  

### ④ 出力先 CSV を保存するフォルダを指定  

### ⑤ 「実績」タブで所持ゲーム一覧を確認  

### ⑥ チェックを入れたゲームだけを **Export** ボタンで CSV に書き出し  

<br>

## 📝 注意事項  
- 実績データは Steam API / ゲーム側が公開している内容に依存します  
- 一部ゲームは実績詳細を非公開にしています  
- 所持ゲームのみ取得可能（ファミリーシェアリングは非対応）  
- Steam API Key は無料で取得できます  

---

# <a id="english-version"></a>🇺🇸 English Version  

## What is Steam Achievements Export?  
Steam Achievements Export is a Windows application that allows you to  
**retrieve achievement data for all games you own on Steam and export it into a clean CSV file.**

Using the Steam Web API, the app collects:
- Game title  
- Achievement name  
- Achievement description  
- Unlock status (✓ / ✗)  

The generated CSV can be used in Excel, Google Sheets, or any spreadsheet software for organization and analysis.  
**This application is designed for users who want to manage their Steam achievements using spreadsheets.**

<br>

## 🔹 Supports Japanese Game Titles & Achievement Data  
For supported games, both game names and achievement descriptions can be retrieved in Japanese.  

## 🔹 Automatically Retrieves Owned Games  
Simply enter your API Key and SteamID64—  
the app will list all games owned by your Steam account.  

## 🔹 Search & Filter Games  
Use the search bar to filter your game list in real-time.  

## 🔹 Export Only the Selected Games  
You can export achievements for selected games only,  
with features like **Select All** and **Clear** for convenience.  

<br>

# 📘 How to Use  

### ① Launch the executable and open the **Settings** page  

### ② Obtain your Steam Web API Key  
1. Visit https://steamcommunity.com/dev/apikey  
2. Log in with your Steam account  
3. Enter `localhost` in the Domain field  
4. Click **Register** to receive your API Key  

### ③ Find your SteamID64  
1. Open your Steam profile  
2. Go to https://steamid.io/ and paste your profile URL  
3. Use the displayed **SteamID64 (17 digits)**  

### ④ Choose the output folder for CSV files  

### ⑤ View your owned games in the **Achievements** tab  

### ⑥ Select the games and click **Export** to generate a CSV file  

<br>

## 📝 Notes  
- Achievement data availability depends on what each game exposes through the Steam API  
- Some games do not provide detailed achievement information  
- Only achievements for games you personally own can be retrieved  
- The Steam API Key is free to obtain  

---
