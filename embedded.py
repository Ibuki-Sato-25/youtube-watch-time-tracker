import streamlit.components.v1 as components

class Embedded:
    def __init__(self, logger):
        self.logger = logger

    def video_html(self, video_db_id, video_url, port_number):
        components.html(f"""
        <html>
        <body>
            <!-- YouTube iFrame API をdivで再生するためのコード -->
            <div id="player-{video_db_id}"></div>

            <script>
                var videoUrl = "{video_url}";
                var videoId = "{video_db_id}"; 
                var port = "{port_number}";
                console.log(videoUrl);
                console.log(videoId);
                console.log(port);

                // YouTube Iframe APIの読み込み
                var tag = document.createElement('script');
                tag.src = "https://www.youtube.com/iframe_api";
                var firstScriptTag = document.getElementsByTagName('script')[0];
                firstScriptTag.parentNode.insertBefore(tag, firstScriptTag);

                var player;
                var watchTime = 0;
                var lastTime = 0;
                var startTime;
                var isPlaying = false;

                // YouTube Iframe APIの読み込み完了後に呼ばれる関数
                function onYouTubeIframeAPIReady() {{
                    player = new YT.Player('player-{video_db_id}', {{ // IDをユニークにする
                        height: '396',
                        width: '704',
                        videoId: videoUrl.split("embed/")[1].split("?")[0],
                        events: {{
                            'onStateChange': onPlayerStateChange,
                            'onError': onPlayerError
                        }}
                    }});
                }}

                // プレイヤーの状態が変更されたときに呼ばれる関数
                function onPlayerStateChange(event) {{
                    if (event.data == YT.PlayerState.PLAYING) {{
                        if (!isPlaying) {{
                            startTime = new Date().getTime();
                            isPlaying = true;
                        }}
                    }} else {{
                        if (isPlaying) {{
                            var endTime = new Date().getTime();
                            var elapsed = (endTime - startTime) / 1000;
                            watchTime += elapsed;
                            fetch(`http://localhost:${{port}}/save_watch_time?video_id=${{videoId}}&watch_time=${{watchTime}}`)
                                .then(response => {{
                                    if (!response.ok) {{
                                        throw new Error('Network response was not ok');
                                    }}
                                    return response.json();
                                }})
                                .then(data => {{
                                    console.log('Watch time saved:', data);
                                    watchTime = 0;
                                }})
                                .catch(error => {{
                                    console.error('Error:', error);
                                    // エラーレスポンスがHTMLの場合、内容をログに出力
                                    error.text().then(errorMessage => console.error('Error message:', errorMessage));
                                }});
                            isPlaying = false;
                        }}
                    }}
                }}

                // プレイヤーのエラーが発生したときに呼ばれる関数
                function onPlayerError(event) {{
                    console.error('Error:', event);
                }}
            </script>
        </body>
        </html>
        """, height=400)
        self.logger.info(f'Video URL: {video_url} from embedded.py')
        self.logger.info(f'Video ID: {video_db_id} from embedded.py')
        self.logger.info(f'Port number: {port_number} from embedded.py')