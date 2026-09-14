# Picoさん、Egonさんへの報告
## TODO超ドラフトなので、後で丁寧に書き直す

こんにちは、今週日本では国内版BioHackathonが大分県の別府で開催されました。
我々Pathwayチームの数名は以下のような開発と検証を行いました。

1. Wikipathways -> Wikipathways（多種）のリフトオーバーツール（PathLift）の開発といくつかの種で検証を行いました。
- PathLift: 
- 

2. Cyc_to_wiki, 新しいPathVisioの現状での対応を状況を実際に変換を行い調べました。
- PathVisio 4.0: https://github.com/PathVisio/pathvisio4-ant/  これを試しています
- 

3. Cyc_to_wikiで変換したGPMLを対象に、良い感じのレイアウト当て直すをPathLayを開発しました。
PathLay: https://github.com/dogrun-inc/PathLay
PathLayはGPMLのノード、エッジ情報からグラフ構造を生成し幅優先探索のアルゴリズムを用いGPMLのレイアウトを作り直します。シンプルなパスウェイであれば整った印象のレイアウトを生成できるのではないかと思います。

今回のプロジェクトに参加したメンバーの疑問ですが
今後WikiPathwaysのデータ登録はGPML2021になる、予定ですかまたGPML2013aは廃止するのでしょうか？
今後について決まったことがあればコメントいただけると嬉しいです

それではまた日本でお会いできるのを楽しみにしています。