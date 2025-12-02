## **Steam Achievements Export とは？**  
Steam で所有しているゲームの実績情報を一括取得し、  
日本語でわかりやすく CSV に書き出せる Windows 専用アプリです。  

Steam API を利用して、  
ゲームタイトル / 実績名 / 実績説明 / 取得状況（✓ / ✗）  
をまとめて取得し、  
Excel や Google スプレッドシートで分析・整理できる形式で出力します。  
<br><br>
  
## 🔹 日本語タイトル・日本語実績に対応  
&nbsp;&nbsp;&nbsp;対応しているゲームは、ゲーム名も実績名も日本語で取得できます。  
<br>
## 🔹 所有ゲームを自動取得  
&nbsp;&nbsp;&nbsp;API Key と SteamID64 を入力するだけで、  
&nbsp;&nbsp;&nbsp;Steam アカウントが所有するすべてのゲームを一覧化します。  
<br>
## 🔹 ゲーム検索・フィルタリング  
&nbsp;&nbsp;&nbsp;上部の検索バーから  
&nbsp;&nbsp;&nbsp;ゲーム一覧をリアルタイムに検索できます。  
<br>
## 🔹 チェックしたゲームだけ書き出し  
&nbsp;&nbsp;&nbsp;「Select All」「Clear」機能に加えて、  
&nbsp;&nbsp;&nbsp;必要なゲームのみを選んで CSV に保存できます。  
<br><br>
<br><br>
## **使用方法**  
⓵exeを起動したら設定ページを開きます。  
<br>
⓶Steam Web APIキーを取得  
&nbsp;&nbsp;&nbsp;1. https://steamcommunity.com/dev/apikeyでAPI Keyを 取得する。  
&nbsp;&nbsp;&nbsp;2. Steamアカウントでログイン  
&nbsp;&nbsp;&nbsp;3. Domain に適当に `localhost` と入力  
&nbsp;&nbsp;&nbsp;4. 「Register」→ API Key が発行される   
<br>
⓷Steam ID を確認  
&nbsp;&nbsp;&nbsp;1. 自分のSteamプロフィールを開く&nbsp;&nbsp;&nbsp;例：https://steamcommunity.com/id/ユーザー名/   
&nbsp;&nbsp;&nbsp;2. SteamID Finder(https://steamid.io/) にそのURLを貼る  
&nbsp;&nbsp;&nbsp;3. 「SteamID64（17桁の数字）」  
<br>
⓸出力先CSVに、CSVを出力したいフォルダを選びます。         
<br>
⓹実績タブに所持しているゲーム一覧が表示されます。  
<br>
⓺チェックボックスにチェックを入れ、Exportボタンで指定したフォルダにcsvファイルが生成されます。  
<br>
  
## 📝 注意事項  
&nbsp;&nbsp;&nbsp;実績データは Steam API / ゲーム側が公開している範囲で取得されます。  
&nbsp;&nbsp;&nbsp;一部ゲームは実績の詳細情報を公開していない場合があります。  
&nbsp;&nbsp;&nbsp;自身の所持しているゲームの実績のみ取得できます。ファミリーシェアリングをしているゲームは取得できません。  
&nbsp;&nbsp;&nbsp;Steam API Key は無料で取得できます。  
