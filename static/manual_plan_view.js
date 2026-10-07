document.addEventListener(
    "DOMContentLoaded",
    function () {

        const HISTORY_KEY =
            "chichibuTravelPlanHistoryV1";


        const DRAFT_KEY =
            "chichibuManualPlanDraftV1";


        const TRIP_BOOK_DRAFT_KEY =
            "chichibuTripBookDraftV1";



        function getElement(
            id
        ) {

            return document.getElementById(
                id
            );

        }



        function safeParse(
            raw,
            fallback
        ) {

            try {

                const value =
                    JSON.parse(
                        raw
                    );


                return (
                    value == null
                    ?
                    fallback
                    :
                    value
                );

            }

            catch (
                error
            ) {

                return fallback;

            }

        }



        function escapeHtml(
            value
        ) {

            return String(
                value == null
                ?
                ""
                :
                value
            )

            .replace(
                /&/g,
                "&amp;"
            )

            .replace(
                /</g,
                "&lt;"
            )

            .replace(
                />/g,
                "&gt;"
            )

            .replace(
                /"/g,
                "&quot;"
            )

            .replace(
                /'/g,
                "&#039;"
            );

        }



        const params =
            new URLSearchParams(
                location.search
            );


        let plan =
            null;



        /* =====================================================
           下書きプレビュー
        ====================================================== */

        if (
            params.get(
                "draft"
            )
            ===
            "1"
        ) {

            const draft =
                safeParse(
                    localStorage.getItem(
                        DRAFT_KEY
                    ),
                    null
                );


            if (
                draft
                &&
                draft.state
            ) {

                plan =
                    draft.state;

            }

        }



        /* =====================================================
           保存済みプラン
        ====================================================== */

        else {

            const planId =
                params.get(
                    "id"
                );


            const history =
                safeParse(
                    localStorage.getItem(
                        HISTORY_KEY
                    ),
                    []
                );


            if (
                Array.isArray(
                    history
                )
            ) {

                plan =
                    history.find(
                        function (
                            item
                        ) {

                            return (

                                item

                                &&

                                item.id
                                ===
                                planId

                                &&

                                item.planType
                                ===
                                "manual"

                            );

                        }
                    )
                    ||
                    null;

            }

        }



        /* =====================================================
           プランなし
        ====================================================== */

        if (
            !plan
        ) {

            getElement(
                "title"
            )
            .textContent =
                "プランが見つかりません";


            getElement(
                "sub"
            )
            .textContent =
                "旅行プラン履歴からもう一度開いてください。";


            return;

        }



        /* =====================================================
           DAY数
        ====================================================== */

        const dayCount =

            plan.days
            ===
            "2泊3日"

            ?

            3

            :

            2;



        /* =====================================================
           日付
        ====================================================== */

        function getDateForDay(
            dayNumber
        ) {

            if (
                !plan.travel_date
            ) {

                return "";

            }


            const date =
                new Date(
                    plan.travel_date
                    +
                    "T00:00:00"
                );


            if (
                Number.isNaN(
                    date.getTime()
                )
            ) {

                return "";

            }


            date.setDate(

                date.getDate()

                +

                dayNumber

                -

                1

            );


            return (
                new Intl.DateTimeFormat(
                    "ja-JP",
                    {

                        month:
                            "long",

                        day:
                            "numeric"

                    }
                )
                .format(
                    date
                )
            );

        }



        /* =====================================================
           TITLE
        ====================================================== */

        getElement(
            "title"
        )
        .textContent =

            plan.title

            ||

            "自分で作った秩父旅行";



        /* =====================================================
           SUB TITLE
        ====================================================== */

        const subTexts =
            [

                plan.travel_date || "",

                plan.days || "",

                plan.member || "",

                plan.people
                ?
                plan.people
                +
                "人"
                :
                "",

                plan.car
                ?
                "車"
                +
                plan.car
                :
                ""

            ]
            .filter(
                Boolean
            );


        getElement(
            "sub"
        )
        .textContent =
            subTexts.join(
                " · "
            );



        /* =====================================================
           編集URL
        ====================================================== */

        const editUrl =

            "/manual-plan?edit="

            +

            encodeURIComponent(
                plan.id
                ||
                ""
            );


        getElement(
            "editTop"
        )
        .href =
            editUrl;


        getElement(
            "editBottom"
        )
        .href =
            editUrl;



        /* =====================================================
           OVERVIEW
        ====================================================== */

        const overviewData =
            [

                [
                    "DATE",
                    plan.travel_date
                    ||
                    "未設定"
                ],

                [
                    "DAYS",
                    plan.days
                    ||
                    "—"
                ],

                [
                    "MEMBER",
                    (
                        plan.member
                        ||
                        "—"
                    )
                    +
                    " / "
                    +
                    (
                        plan.people
                        ||
                        "—"
                    )
                    +
                    "人"
                ],

                [
                    "CAR",
                    plan.car
                    ||
                    "—"
                ]

            ];


        getElement(
            "overview"
        )
        .innerHTML =

            overviewData
            .map(
                function (
                    item
                ) {

                    return (

                        "<div>"

                        +

                        "<small>"
                        +
                        escapeHtml(
                            item[
                                0
                            ]
                        )
                        +
                        "</small>"

                        +

                        "<strong>"
                        +
                        escapeHtml(
                            item[
                                1
                            ]
                        )
                        +
                        "</strong>"

                        +

                        "</div>"

                    );

                }
            )
            .join(
                ""
            );



        /* =====================================================
           TRIP MEMO
        ====================================================== */

        if (
            plan.tripMemo
        ) {

            const tripNote =
                getElement(
                    "tripNote"
                );


            tripNote.hidden =
                false;


            tripNote
            .querySelector(
                "p"
            )
            .textContent =
                plan.tripMemo;

        }



        /* =====================================================
           CATEGORY ICON
        ====================================================== */

        function getCategoryIcon(
            category
        ) {

            if (
                category
                ===
                "観光地"
            ) {

                return "🏞";

            }


            if (
                category
                ===
                "飲食店"
            ) {

                return "🍴";

            }


            if (
                category
                ===
                "宿泊施設"
            ) {

                return "🏨";

            }


            return "•";

        }



        /* =====================================================
           DAY RENDER
        ====================================================== */

        const daysContainer =
            getElement(
                "days"
            );


        for (
            let day = 1;
            day <= dayCount;
            day++
        ) {

            const dayKey =
                "day"
                +
                day;


            const items =

                Array.isArray(
                    plan[
                        dayKey
                    ]
                )

                ?

                plan[
                    dayKey
                ]

                :

                [];



            const section =
                document.createElement(
                    "section"
                );


            section.className =
                "day";


            section.innerHTML =

                '<div class="day-head">'

                +

                '<div>'

                +

                '<div class="label">'
                +
                'DAY '
                +
                String(
                    day
                )
                .padStart(
                    2,
                    "0"
                )
                +
                '</div>'

                +

                '<h2>'
                +
                'Day '
                +
                day
                +
                '</h2>'

                +

                '</div>'

                +

                '<div class="day-date">'
                +
                escapeHtml(
                    getDateForDay(
                        day
                    )
                )
                +
                '</div>'

                +

                '</div>'

                +

                '<div class="timeline"></div>';



            const timeline =
                section.querySelector(
                    ".timeline"
                );



            /* 空 */

            if (
                !items.length
            ) {

                timeline.innerHTML =

                    '<div class="empty">'
                    +
                    'このDAYには予定がありません。'
                    +
                    '</div>';

            }



            /* 予定 */

            items.forEach(
                function (
                    item
                ) {

                    const category =

                        item.category

                        ||

                        item.type

                        ||

                        "施設";


                    const icon =
                        getCategoryIcon(
                            category
                        );


                    const row =
                        document.createElement(
                            "article"
                        );


                    row.className =
                        "item";



                    const mapButton =

                        item.map_url

                        ?

                        '<a'
                        +
                        ' class="maps"'
                        +
                        ' href="'
                        +
                        escapeHtml(
                            item.map_url
                        )
                        +
                        '"'
                        +
                        ' target="_blank"'
                        +
                        ' rel="noopener"'
                        +
                        '>'
                        +
                        'GOOGLE MAPS ↗'
                        +
                        '</a>'

                        :

                        "";



                    row.innerHTML =

                        '<div class="time">'
                        +
                        escapeHtml(
                            item.timeOfDay
                            ||
                            "--:--"
                        )
                        +
                        '</div>'

                        +

                        '<div class="card">'

                        +

                        '<div class="type">'
                        +
                        escapeHtml(
                            icon
                        )
                        +
                        " "
                        +
                        escapeHtml(
                            category
                        )
                        +
                        '</div>'

                        +

                        '<h3>'
                        +
                        escapeHtml(
                            item.name
                        )
                        +
                        '</h3>'

                        +

                        (
                            item.role
                            ?
                            '<span class="role">'
                            +
                            escapeHtml(
                                item.role
                            )
                            +
                            '</span>'
                            :
                            ""
                        )

                        +

                        (
                            item.memo
                            ?
                            '<p class="memo">'
                            +
                            escapeHtml(
                                item.memo
                            )
                            +
                            '</p>'
                            :
                            ""
                        )

                        +

                        mapButton

                        +

                        '</div>';



                    timeline.appendChild(
                        row
                    );

                }
            );


            daysContainer.appendChild(
                section
            );

        }



        /* =====================================================
           TRIP BOOK用データへ変換
        ====================================================== */

        function convertToTripBookPlan() {

            const sourcePlan = {

                schemaVersion:
                    1,

                people:
                    plan.people,

                member:
                    plan.member,

                car:
                    plan.car,

                days:
                    plan.days,

                travel_date:
                    plan.travel_date,

                purpose:
                    [],

                trip_style:
                    plan.title
                    ||
                    "MY PLAN",

                trip_summary:
                    plan.tripMemo
                    ||
                    "",

                day1:
                    [],

                day2:
                    [],

                day3:
                    [],

                recommended_restaurants:
                    [],

                hotel:
                    null,

                other_hotels:
                    []

            };



            for (
                let day = 1;
                day <= dayCount;
                day++
            ) {

                const key =
                    "day"
                    +
                    day;


                const items =

                    Array.isArray(
                        plan[
                            key
                        ]
                    )

                    ?

                    plan[
                        key
                    ]

                    :

                    [];



                items.forEach(
                    function (
                        item
                    ) {

                        const copy =
                            JSON.parse(
                                JSON.stringify(
                                    item
                                )
                            );


                        if (
                            copy.category
                            ===
                            "飲食店"
                        ) {

                            sourcePlan
                            .recommended_restaurants
                            .push(
                                copy
                            );

                        }

                        else if (
                            copy.category
                            ===
                            "宿泊施設"
                        ) {

                            if (
                                !sourcePlan.hotel
                            ) {

                                sourcePlan.hotel =
                                    copy;

                            }

                            else {

                                sourcePlan
                                .other_hotels
                                .push(
                                    copy
                                );

                            }

                        }

                        else {

                            sourcePlan[
                                key
                            ]
                            .push(
                                copy
                            );

                        }

                    }
                );

            }


            return sourcePlan;

        }



        /* =====================================================
           TRIP BOOK
        ====================================================== */

        getElement(
            "tripBookButton"
        )
        .addEventListener(
            "click",
            function () {

                const sourcePlan =
                    convertToTripBookPlan();


                try {

                    localStorage.setItem(

                        TRIP_BOOK_DRAFT_KEY,

                        JSON.stringify(
                            {

                                sourcePlan:
                                    sourcePlan,

                                createdAt:
                                    new Date()
                                        .toISOString()

                            }
                        )

                    );

                }

                catch (
                    error
                ) {

                    console.error(
                        "TRIP BOOKデータ保存エラー:",
                        error
                    );


                    return;

                }


                location.href =
                    "/trip-book";

            }
        );

    }
);