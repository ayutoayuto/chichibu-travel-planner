document.addEventListener(
    "DOMContentLoaded",
    function () {

        "use strict";


        /* =====================================================
           STORAGE KEY
        ====================================================== */

        const HISTORY_KEY =
            "chichibuTravelPlanHistoryV1";


        const FAVORITES_KEY =
            "chichibuTravelFavoritesV1";


        const DRAFT_KEY =
            "chichibuManualPlanDraftV1";



        /* =====================================================
           FLASK DATA
        ====================================================== */

        const catalogElement =
            document.getElementById(
                "manualCatalogData"
            );


        let catalog = {};


        try {

            catalog =
                JSON.parse(
                    catalogElement
                        ?
                        catalogElement.textContent
                        :
                        "{}"
                ) || {};

        }

        catch (error) {

            console.error(
                "施設データ読み込みエラー:",
                error
            );


            catalog = {};

        }



        /* =====================================================
           DOM
        ====================================================== */

        function getElement(
            id
        ) {

            return document.getElementById(
                id
            );

        }


        const refs = {

            title:
                getElement(
                    "planTitle"
                ),

            date:
                getElement(
                    "travelDate"
                ),

            days:
                getElement(
                    "travelDays"
                ),

            people:
                getElement(
                    "people"
                ),

            member:
                getElement(
                    "member"
                ),

            car:
                getElement(
                    "car"
                ),

            memo:
                getElement(
                    "tripMemo"
                ),

            search:
                getElement(
                    "facilitySearch"
                ),

            grid:
                getElement(
                    "facilityGrid"
                ),

            count:
                getElement(
                    "facilityResultCount"
                ),

            filterTabs:
                getElement(
                    "filterTabs"
                ),

            addDay:
                getElement(
                    "addDaySelect"
                ),

            daysContainer:
                getElement(
                    "daysContainer"
                ),

            save:
                getElement(
                    "savePlanButton"
                ),

            preview:
                getElement(
                    "previewButton"
                ),

            saveMessage:
                getElement(
                    "saveMessage"
                ),

            draftStatus:
                getElement(
                    "draftStatus"
                ),

            favoriteCount:
                getElement(
                    "favoriteCount"
                ),

            clear:
                getElement(
                    "clearPlanButton"
                ),

            detailModal:
                getElement(
                    "detailModal"
                ),

            detailClose:
                getElement(
                    "detailClose"
                ),

            detailContent:
                getElement(
                    "detailContent"
                ),

            draftModal:
                getElement(
                    "draftModal"
                ),

            continueDraft:
                getElement(
                    "continueDraftButton"
                ),

            newDraft:
                getElement(
                    "newDraftButton"
                )

        };



        /* =====================================================
           STATE
        ====================================================== */

        let currentFilter =
            "all";


        let editingId =
            null;


        let createdAt =
            null;


        let state =
            createBlankState();



        function createBlankState() {

            return {

                schemaVersion:
                    2,

                planType:
                    "manual",

                id:
                    null,

                title:
                    "",

                travel_date:
                    "",

                days:
                    "1泊2日",

                people:
                    2,

                member:
                    "友人",

                car:
                    "なし",

                tripMemo:
                    "",

                day1:
                    [],

                day2:
                    [],

                day3:
                    []

            };

        }



        /* =====================================================
           COMMON
        ====================================================== */

        function clone(
            value
        ) {

            return JSON.parse(
                JSON.stringify(
                    value
                )
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

            catch (error) {

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



        function makeId(
            prefix
        ) {

            return (

                prefix
                +
                "-"
                +
                Date.now()
                +
                "-"
                +
                Math.random()
                    .toString(36)
                    .slice(
                        2,
                        8
                    )

            );

        }



        /* =====================================================
           HISTORY
        ====================================================== */

        function readHistory() {

            const value =
                safeParse(
                    localStorage.getItem(
                        HISTORY_KEY
                    ),
                    []
                );


            return (
                Array.isArray(
                    value
                )
                ?
                value
                :
                []
            );

        }


        function writeHistory(
            history
        ) {

            try {

                localStorage.setItem(
                    HISTORY_KEY,
                    JSON.stringify(
                        history
                    )
                );


                return true;

            }

            catch (error) {

                console.error(
                    "旅行プラン履歴保存エラー:",
                    error
                );


                return false;

            }

        }



        /* =====================================================
           FAVORITES
        ====================================================== */

        function readFavorites() {

            const value =
                safeParse(
                    localStorage.getItem(
                        FAVORITES_KEY
                    ),
                    []
                );


            return (
                Array.isArray(
                    value
                )
                ?
                value
                :
                []
            );

        }


        function favoriteKey(
            item
        ) {

            return [

                item.type || "",

                item.name || "",

                item.address || ""

            ]
            .join(
                "|"
            );

        }



        /* =====================================================
           DAY
        ====================================================== */

        function getDayCount() {

            return (
                state.days
                ===
                "2泊3日"
                ?
                3
                :
                2
            );

        }


        function getDayKey(
            day
        ) {

            return (
                "day"
                +
                day
            );

        }



        /* =====================================================
           CATALOG
        ====================================================== */

        function normalizeCatalog() {

            const result =
                [];


            [

                "観光地",

                "飲食店",

                "宿泊施設"

            ]
            .forEach(
                function (
                    type
                ) {

                    const rows =

                        Array.isArray(
                            catalog[
                                type
                            ]
                        )

                        ?

                        catalog[
                            type
                        ]

                        :

                        [];


                    rows
                    .forEach(
                        function (
                            item,
                            index
                        ) {

                            const copy =
                                clone(
                                    item
                                );


                            copy.type =
                                type;


                            copy._catalogId =
                                [

                                    type,

                                    copy.name || "",

                                    copy.address || "",

                                    index

                                ]
                                .join(
                                    "|"
                                );


                            result.push(
                                copy
                            );

                        }
                    );

                }
            );


            return result;

        }


        const allFacilities =
            normalizeCatalog();



        /* =====================================================
           TYPE
        ====================================================== */

        function getDefaultRole(
            type
        ) {

            if (
                type
                ===
                "飲食店"
            ) {

                return "昼食";

            }


            if (
                type
                ===
                "宿泊施設"
            ) {

                return "宿泊";

            }


            return "観光";

        }


        function getCategoryIcon(
            type
        ) {

            if (
                type
                ===
                "観光地"
            ) {

                return "🏞";

            }


            if (
                type
                ===
                "飲食店"
            ) {

                return "🍴";

            }


            return "🏨";

        }



        /* =====================================================
           INPUT → STATE
        ====================================================== */

        function syncStateFromInputs() {

            state.title =
                refs.title.value.trim();


            state.travel_date =
                refs.date.value;


            const previousDays =
                state.days;


            state.days =
                refs.days.value;


            state.people =
                Number(
                    refs.people.value
                )
                ||
                1;


            state.member =
                refs.member.value;


            state.car =
                refs.car.value;


            state.tripMemo =
                refs.memo.value;


            if (
                previousDays
                !==
                state.days
                &&
                getDayCount()
                ===
                2
            ) {

                state.day3 =
                    [];

            }

        }



        /* =====================================================
           STATE → INPUT
        ====================================================== */

        function syncInputsFromState() {

            refs.title.value =
                state.title
                ||
                "";


            refs.date.value =
                state.travel_date
                ||
                "";


            refs.days.value =
                state.days
                ||
                "1泊2日";


            refs.people.value =
                String(
                    state.people
                    ||
                    2
                );


            refs.member.value =
                state.member
                ||
                "友人";


            refs.car.value =
                state.car
                ||
                "なし";


            refs.memo.value =
                state.tripMemo
                ||
                "";

        }



        /* =====================================================
           DATE
        ====================================================== */

        function getPlanDate(
            day
        ) {

            if (
                !state.travel_date
            ) {

                return "";

            }


            const date =
                new Date(
                    state.travel_date
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
                day
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
           DAY SELECT
        ====================================================== */

        function updateDaySelect() {

            refs.addDay.innerHTML =
                "";


            for (
                let day = 1;
                day <= getDayCount();
                day++
            ) {

                const option =
                    document.createElement(
                        "option"
                    );


                option.value =
                    String(
                        day
                    );


                option.textContent =
                    "DAY "
                    +
                    day;


                refs.addDay.appendChild(
                    option
                );

            }

        }



        /* =====================================================
           FACILITY LIST
        ====================================================== */

        function renderFacilities() {

            const favorites =
                readFavorites();


            const favoriteKeys =
                new Set(
                    favorites.map(
                        favoriteKey
                    )
                );


            refs.favoriteCount.textContent =
                String(
                    favorites.length
                );


            const keyword =
                refs.search.value
                    .trim()
                    .toLowerCase();



            const facilities =
                allFacilities.filter(
                    function (
                        item
                    ) {

                        if (
                            currentFilter
                            ===
                            "favorite"
                            &&
                            !favoriteKeys.has(
                                favoriteKey(
                                    item
                                )
                            )
                        ) {

                            return false;

                        }


                        if (
                            ![
                                "all",
                                "favorite"
                            ]
                            .includes(
                                currentFilter
                            )
                            &&
                            item.type
                            !==
                            currentFilter
                        ) {

                            return false;

                        }


                        if (
                            !keyword
                        ) {

                            return true;

                        }


                        const searchable =
                            [

                                item.name,

                                item.area,

                                item.description,

                                item.category_detail,

                                item.genre,

                                item.hours,

                                item.price

                            ]

                            .filter(
                                Boolean
                            )

                            .join(
                                " "
                            )

                            .toLowerCase();


                        return searchable.includes(
                            keyword
                        );

                    }
                );



            refs.count.textContent =
                facilities.length
                +
                "件";


            refs.grid.innerHTML =
                "";



            if (
                !facilities.length
            ) {

                refs.grid.innerHTML =

                    '<div class="empty-result">'
                    +
                    '条件に合う施設がありません。'
                    +
                    '<br>'
                    +
                    '検索条件やカテゴリを変更してください。'
                    +
                    '</div>';


                return;

            }



            facilities.forEach(
                function (
                    item
                ) {

                    const isFavorite =
                        favoriteKeys.has(
                            favoriteKey(
                                item
                            )
                        );


                    const card =
                        document.createElement(
                            "article"
                        );


                    card.className =
                        "facility-card";


                    card.innerHTML =

                        '<div class="type">'
                        +
                        escapeHtml(
                            getCategoryIcon(
                                item.type
                            )
                        )
                        +
                        " "
                        +
                        escapeHtml(
                            item.type
                        )
                        +
                        '</div>'

                        +

                        (
                            isFavorite
                            ?
                            '<div class="favorite-mark">♥ お気に入り</div>'
                            :
                            ""
                        )

                        +

                        '<h3>'
                        +
                        escapeHtml(
                            item.name
                        )
                        +
                        '</h3>'

                        +

                        '<div class="facility-area">'
                        +
                        escapeHtml(
                            item.area
                            ||
                            ""
                        )
                        +
                        '</div>'

                        +

                        '<p class="facility-desc">'
                        +
                        escapeHtml(
                            item.description
                            ||
                            "登録済み施設情報から選択できます。"
                        )
                        +
                        '</p>'

                        +

                        '<div class="card-actions">'

                        +

                        '<button type="button" class="detail-btn">'
                        +
                        '詳細を見る'
                        +
                        '</button>'

                        +

                        '<button type="button" class="add-btn">'
                        +
                        'プランに追加'
                        +
                        '</button>'

                        +

                        '</div>';



                    card
                    .querySelector(
                        ".detail-btn"
                    )
                    .addEventListener(
                        "click",
                        function () {

                            openDetail(
                                item
                            );

                        }
                    );



                    card
                    .querySelector(
                        ".add-btn"
                    )
                    .addEventListener(
                        "click",
                        function () {

                            addFacility(

                                item,

                                Number(
                                    refs.addDay.value
                                )
                                ||
                                1

                            );

                        }
                    );


                    refs.grid.appendChild(
                        card
                    );

                }
            );

        }



        /* =====================================================
           DETAIL
        ====================================================== */

        function detailBox(
            label,
            value
        ) {

            if (
                value === undefined
                ||
                value === null
                ||
                String(
                    value
                )
                .trim()
                ===
                ""
            ) {

                return "";

            }


            return (

                '<div class="detail-box">'

                +

                '<strong>'
                +
                escapeHtml(
                    label
                )
                +
                '</strong>'

                +

                '<span>'
                +
                escapeHtml(
                    value
                )
                +
                '</span>'

                +

                '</div>'

            );

        }



        function getAccessText(
            access
        ) {

            if (
                !access
            ) {

                return "";

            }


            if (
                typeof access
                ===
                "string"
            ) {

                return access;

            }


            if (
                typeof access
                !==
                "object"
            ) {

                return "";

            }


            return [

                access.train
                ?
                "電車：" + access.train
                :
                "",

                access.bus
                ?
                "バス：" + access.bus
                :
                "",

                access.walk
                ?
                "徒歩：" + access.walk
                :
                "",

                access.car
                ?
                "車：" + access.car
                :
                ""

            ]

            .filter(
                Boolean
            )

            .join(
                "\n"
            );

        }



        function openDetail(
            item
        ) {

            const mapButton =

                item.map_url

                ?

                '<a'
                +
                ' class="primary-action"'
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
                'Google Maps ↗'
                +
                '</a>'

                :

                "";



            refs.detailContent.innerHTML =

                '<div class="section-kicker">'
                +
                escapeHtml(
                    getCategoryIcon(
                        item.type
                    )
                )
                +
                " "
                +
                escapeHtml(
                    item.type
                )
                +
                ' · FACILITY DETAIL'
                +
                '</div>'

                +

                '<h2>'
                +
                escapeHtml(
                    item.name
                )
                +
                '</h2>'

                +

                '<p>'
                +
                escapeHtml(
                    item.description
                    ||
                    ""
                )
                +
                '</p>'

                +

                '<div class="detail-grid">'

                +

                detailBox(
                    "AREA",
                    item.area
                )

                +

                detailBox(
                    "ADDRESS",
                    item.address
                )

                +

                detailBox(
                    "ACCESS",
                    getAccessText(
                        item.access
                    )
                )

                +

                detailBox(
                    "HOURS",
                    item.hours
                )

                +

                detailBox(
                    "PRICE",
                    item.price
                )

                +

                detailBox(
                    "CLOSED",
                    item.closed
                )

                +

                detailBox(
                    "PARKING",
                    item.parking
                )

                +

                detailBox(
                    "SEASON",
                    item.season
                )

                +

                '</div>'

                +

                (
                    item.notes
                    ?
                    '<p>'
                    +
                    escapeHtml(
                        item.notes
                    )
                    +
                    '</p>'
                    :
                    ""
                )

                +

                '<div class="modal-actions">'

                +

                '<button'
                +
                ' type="button"'
                +
                ' class="secondary-action"'
                +
                ' id="detailAddButton"'
                +
                '>'
                +
                'DAY'
                +
                (
                    Number(
                        refs.addDay.value
                    )
                    ||
                    1
                )
                +
                'に追加'
                +
                '</button>'

                +

                mapButton

                +

                '</div>';



            const addButton =
                getElement(
                    "detailAddButton"
                );


            if (
                addButton
            ) {

                addButton.addEventListener(
                    "click",
                    function () {

                        addFacility(

                            item,

                            Number(
                                refs.addDay.value
                            )
                            ||
                            1

                        );


                        closeModal(
                            refs.detailModal
                        );

                    }
                );

            }


            openModal(
                refs.detailModal
            );

        }



        /* =====================================================
           ADD FACILITY
        ====================================================== */

        function addFacility(
            item,
            day
        ) {

            if (
                day < 1
                ||
                day > getDayCount()
            ) {

                day =
                    1;

            }


            const schedule =
                clone(
                    item
                );


            schedule.scheduleId =
                makeId(
                    "schedule"
                );


            schedule.category =
                item.type;


            schedule.role =
                getDefaultRole(
                    item.type
                );


            schedule.timeOfDay =
                "";


            schedule.memo =
                "";


            state[
                getDayKey(
                    day
                )
            ]
            .push(
                schedule
            );


            changed();

        }



        /* =====================================================
           MOVE / DELETE
        ====================================================== */

        function moveWithinDay(
            day,
            index,
            direction
        ) {

            const array =
                state[
                    getDayKey(
                        day
                    )
                ];


            const nextIndex =
                index
                +
                direction;


            if (
                nextIndex < 0
                ||
                nextIndex
                >=
                array.length
            ) {

                return;

            }


            const temp =
                array[
                    index
                ];


            array[
                index
            ] =
                array[
                    nextIndex
                ];


            array[
                nextIndex
            ] =
                temp;


            changed();

        }



        function removeItem(
            day,
            index
        ) {

            state[
                getDayKey(
                    day
                )
            ]
            .splice(
                index,
                1
            );


            changed();

        }



        function moveToAnotherDay(
            day,
            index,
            targetDay
        ) {

            if (
                targetDay
                ===
                day
            ) {

                return;

            }


            const sourceArray =
                state[
                    getDayKey(
                        day
                    )
                ];


            const item =
                sourceArray.splice(
                    index,
                    1
                )[0];


            if (
                item
            ) {

                state[
                    getDayKey(
                        targetDay
                    )
                ]
                .push(
                    item
                );

            }


            changed();

        }



        /* =====================================================
           RENDER DAYS
        ====================================================== */

        function renderDays() {

            updateDaySelect();


            refs.daysContainer.innerHTML =
                "";


            for (
                let day = 1;
                day <= getDayCount();
                day++
            ) {

                const array =
                    state[
                        getDayKey(
                            day
                        )
                    ];


                const block =
                    document.createElement(
                        "section"
                    );


                block.className =
                    "day-block";


                block.innerHTML =

                    '<div class="day-title-row">'

                    +

                    '<div>'

                    +

                    '<div class="day-label">'
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

                    '<h3>'
                    +
                    'Day '
                    +
                    day
                    +
                    '</h3>'

                    +

                    '</div>'

                    +

                    '<div class="day-date">'
                    +
                    escapeHtml(
                        getPlanDate(
                            day
                        )
                    )
                    +
                    '</div>'

                    +

                    '</div>'

                    +

                    '<div class="day-list"></div>';



                const list =
                    block.querySelector(
                        ".day-list"
                    );



                if (
                    !array.length
                ) {

                    list.innerHTML =

                        '<div class="empty-day">'
                        +
                        'まだ予定がありません。'
                        +
                        '<br>'
                        +
                        '左の施設一覧から追加してください。'
                        +
                        '</div>';

                }

                else {

                    array.forEach(
                        function (
                            item,
                            index
                        ) {

                            const row =
                                document.createElement(
                                    "article"
                                );


                            row.className =
                                "schedule-item";



                            const moveOptions =
                                [];


                            for (
                                let target = 1;
                                target <= getDayCount();
                                target++
                            ) {

                                moveOptions.push(

                                    '<option value="'
                                    +
                                    target
                                    +
                                    '" '
                                    +
                                    (
                                        target === day
                                        ?
                                        "selected"
                                        :
                                        ""
                                    )
                                    +
                                    '>'
                                    +
                                    'DAY '
                                    +
                                    target
                                    +
                                    '</option>'

                                );

                            }



                            let roles =
                                [];


                            if (
                                item.category
                                ===
                                "飲食店"
                            ) {

                                roles = [

                                    "朝食",

                                    "昼食",

                                    "カフェ",

                                    "夕食"

                                ];

                            }

                            else if (
                                item.category
                                ===
                                "宿泊施設"
                            ) {

                                roles = [

                                    "宿泊"

                                ];

                            }

                            else {

                                roles = [

                                    "観光"

                                ];

                            }



                            row.innerHTML =

                                '<div class="schedule-top">'

                                +

                                '<input'
                                +
                                ' class="time-input"'
                                +
                                ' type="time"'
                                +
                                ' value="'
                                +
                                escapeHtml(
                                    item.timeOfDay
                                    ||
                                    ""
                                )
                                +
                                '"'
                                +
                                ' aria-label="予定時刻"'
                                +
                                '>'

                                +

                                '<div>'

                                +

                                '<div class="schedule-type">'
                                +
                                escapeHtml(
                                    getCategoryIcon(
                                        item.category
                                    )
                                )
                                +
                                " "
                                +
                                escapeHtml(
                                    item.category
                                )
                                +
                                '</div>'

                                +

                                '<h4 class="schedule-name">'
                                +
                                escapeHtml(
                                    item.name
                                )
                                +
                                '</h4>'

                                +

                                '</div>'

                                +

                                '<div class="schedule-actions">'

                                +

                                '<button'
                                +
                                ' type="button"'
                                +
                                ' data-action="up"'
                                +
                                ' title="上へ"'
                                +
                                '>'
                                +
                                '↑'
                                +
                                '</button>'

                                +

                                '<button'
                                +
                                ' type="button"'
                                +
                                ' data-action="down"'
                                +
                                ' title="下へ"'
                                +
                                '>'
                                +
                                '↓'
                                +
                                '</button>'

                                +

                                '</div>'

                                +

                                '</div>'

                                +

                                '<div class="schedule-edit-row">'

                                +

                                '<select class="role-select">'

                                +

                                roles
                                .map(
                                    function (
                                        role
                                    ) {

                                        return (

                                            '<option '
                                            +
                                            (
                                                role
                                                ===
                                                item.role
                                                ?
                                                "selected"
                                                :
                                                ""
                                            )
                                            +
                                            '>'
                                            +
                                            escapeHtml(
                                                role
                                            )
                                            +
                                            '</option>'

                                        );

                                    }
                                )
                                .join(
                                    ""
                                )

                                +

                                '</select>'

                                +

                                '<input'
                                +
                                ' class="memo-input"'
                                +
                                ' type="text"'
                                +
                                ' maxlength="100"'
                                +
                                ' value="'
                                +
                                escapeHtml(
                                    item.memo
                                    ||
                                    ""
                                )
                                +
                                '"'
                                +
                                ' placeholder="この予定のメモ"'
                                +
                                '>'

                                +

                                '</div>'

                                +

                                '<div class="schedule-bottom">'

                                +

                                '<select class="move-select">'

                                +

                                moveOptions
                                .join(
                                    ""
                                )

                                +

                                '</select>'

                                +

                                '<button'
                                +
                                ' type="button"'
                                +
                                ' class="remove-btn"'
                                +
                                '>'
                                +
                                '削除'
                                +
                                '</button>'

                                +

                                '</div>';



                            row
                            .querySelector(
                                ".time-input"
                            )
                            .addEventListener(
                                "change",
                                function (
                                    event
                                ) {

                                    item.timeOfDay =
                                        event.target.value;


                                    saveDraft();

                                }
                            );



                            row
                            .querySelector(
                                ".role-select"
                            )
                            .addEventListener(
                                "change",
                                function (
                                    event
                                ) {

                                    item.role =
                                        event.target.value;


                                    saveDraft();

                                }
                            );



                            row
                            .querySelector(
                                ".memo-input"
                            )
                            .addEventListener(
                                "input",
                                function (
                                    event
                                ) {

                                    item.memo =
                                        event.target.value;


                                    saveDraftDebounced();

                                }
                            );



                            row
                            .querySelector(
                                '[data-action="up"]'
                            )
                            .addEventListener(
                                "click",
                                function () {

                                    moveWithinDay(

                                        day,

                                        index,

                                        -1

                                    );

                                }
                            );



                            row
                            .querySelector(
                                '[data-action="down"]'
                            )
                            .addEventListener(
                                "click",
                                function () {

                                    moveWithinDay(

                                        day,

                                        index,

                                        1

                                    );

                                }
                            );



                            row
                            .querySelector(
                                ".move-select"
                            )
                            .addEventListener(
                                "change",
                                function (
                                    event
                                ) {

                                    moveToAnotherDay(

                                        day,

                                        index,

                                        Number(
                                            event.target.value
                                        )

                                    );

                                }
                            );



                            row
                            .querySelector(
                                ".remove-btn"
                            )
                            .addEventListener(
                                "click",
                                function () {

                                    removeItem(
                                        day,
                                        index
                                    );

                                }
                            );



                            list.appendChild(
                                row
                            );

                        }
                    );

                }



                refs.daysContainer.appendChild(
                    block
                );

            }

        }



        /* =====================================================
           CHANGED
        ====================================================== */

        function changed() {

            syncStateFromInputs();


            renderDays();


            saveDraft();

        }



        /* =====================================================
           DRAFT
        ====================================================== */

        let draftTimer =
            null;


        function saveDraftDebounced() {

            clearTimeout(
                draftTimer
            );


            draftTimer =
                setTimeout(
                    saveDraft,
                    350
                );

        }



        function saveDraft() {

            syncStateFromInputs();


            try {

                localStorage.setItem(

                    DRAFT_KEY,

                    JSON.stringify(
                        {

                            savedAt:
                                new Date()
                                    .toISOString(),

                            state:
                                state

                        }
                    )

                );


                refs.draftStatus.textContent =
                    "✓ 下書き保存済み";


                setTimeout(
                    function () {

                        refs.draftStatus.textContent =
                            "下書き自動保存";

                    },
                    1200
                );

            }

            catch (error) {

                console.error(
                    "下書き保存エラー:",
                    error
                );


                refs.draftStatus.textContent =
                    "下書き保存失敗";

            }

        }



        /* =====================================================
           LOAD STATE
        ====================================================== */

        function loadState(
            rawState
        ) {

            const base =
                createBlankState();


            state =
                Object.assign(
                    base,
                    clone(
                        rawState
                        ||
                        {}
                    )
                );


            [

                "day1",

                "day2",

                "day3"

            ]
            .forEach(
                function (
                    key
                ) {

                    if (
                        !Array.isArray(
                            state[
                                key
                            ]
                        )
                    ) {

                        state[
                            key
                        ] =
                            [];

                    }

                }
            );


            editingId =
                state.id
                ||
                null;


            createdAt =
                state.createdAt
                ||
                null;


            syncInputsFromState();


            renderDays();


            renderFacilities();


            refs.save.textContent =

                editingId

                ?

                "変更を保存"

                :

                "このプランを保存";

        }



        /* =====================================================
           END DATE
        ====================================================== */

        function getEndDate() {

            if (
                !state.travel_date
            ) {

                return "";

            }


            const date =
                new Date(
                    state.travel_date
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

                getDayCount()

                -

                1

            );


            const year =
                date.getFullYear();


            const month =
                String(
                    date.getMonth()
                    +
                    1
                )
                .padStart(
                    2,
                    "0"
                );


            const day =
                String(
                    date.getDate()
                )
                .padStart(
                    2,
                    "0"
                );


            return (

                year
                +
                "-"
                +
                month
                +
                "-"
                +
                day

            );

        }



        /* =====================================================
           SAVE DATA
        ====================================================== */

        function buildSavePlan() {

            syncStateFromInputs();


            const now =
                new Date()
                    .toISOString();


            const id =

                editingId

                ||

                makeId(
                    "manual-plan"
                );


            return Object.assign(

                clone(
                    state
                ),

                {

                    schemaVersion:
                        2,

                    id:
                        id,

                    planType:
                        "manual",

                    title:
                        state.title
                        ||
                        "自分で作った秩父旅行",

                    savedAt:
                        createdAt
                        ||
                        now,

                    createdAt:
                        createdAt
                        ||
                        now,

                    updatedAt:
                        now,

                    travel_end_date:
                        getEndDate()

                }

            );

        }



        /* =====================================================
           VALIDATE
        ====================================================== */

        function validatePlan() {

            syncStateFromInputs();


            if (
                !state.travel_date
            ) {

                refs.saveMessage.textContent =
                    "旅行予定日を入力してください。";


                refs.date.focus();


                return false;

            }


            const total =

                state.day1.length

                +

                state.day2.length

                +

                (
                    getDayCount()
                    ===
                    3
                    ?
                    state.day3.length
                    :
                    0
                );


            if (
                !total
            ) {

                refs.saveMessage.textContent =
                    "少なくとも1件、施設をプランへ追加してください。";


                return false;

            }


            return true;

        }



        /* =====================================================
           SAVE
        ====================================================== */

        function savePlan(
            openAfterSave
        ) {

            if (
                !validatePlan()
            ) {

                return null;

            }


            const plan =
                buildSavePlan();


            const history =
                readHistory();


            const existingIndex =
                history.findIndex(
                    function (
                        item
                    ) {

                        return (

                            item

                            &&

                            item.id
                            ===
                            plan.id

                        );

                    }
                );


            if (
                existingIndex
                >=
                0
            ) {

                history[
                    existingIndex
                ] =
                    plan;

            }

            else {

                history.unshift(
                    plan
                );

            }


            if (
                !writeHistory(
                    history
                )
            ) {

                refs.saveMessage.textContent =
                    "保存に失敗しました。ブラウザの保存容量を確認してください。";


                return null;

            }


            editingId =
                plan.id;


            createdAt =
                plan.createdAt;


            state =
                clone(
                    plan
                );


            localStorage.removeItem(
                DRAFT_KEY
            );


            refs.save.textContent =
                "変更を保存";


            refs.saveMessage.textContent =
                "✓ 旅行プラン履歴に保存しました。";


            if (
                openAfterSave
            ) {

                location.href =

                    "/manual-plan/view?id="

                    +

                    encodeURIComponent(
                        plan.id
                    );

            }


            return plan;

        }



        /* =====================================================
           PREVIEW
        ====================================================== */

        function previewPlan() {

            if (
                !validatePlan()
            ) {

                return;

            }


            const plan =
                buildSavePlan();


            try {

                localStorage.setItem(

                    DRAFT_KEY,

                    JSON.stringify(
                        {

                            savedAt:
                                new Date()
                                    .toISOString(),

                            state:
                                plan,

                            previewOnly:
                                true

                        }
                    )

                );

            }

            catch (error) {

                console.error(
                    error
                );

            }


            location.href =
                "/manual-plan/view?draft=1";

        }



        /* =====================================================
           MODAL
        ====================================================== */

        function openModal(
            modal
        ) {

            modal.classList.add(
                "is-open"
            );


            modal.setAttribute(
                "aria-hidden",
                "false"
            );

        }


        function closeModal(
            modal
        ) {

            modal.classList.remove(
                "is-open"
            );


            modal.setAttribute(
                "aria-hidden",
                "true"
            );

        }



        /* =====================================================
           NEW PLAN
        ====================================================== */

        function startNewPlan() {

            editingId =
                null;


            createdAt =
                null;


            state =
                createBlankState();


            localStorage.removeItem(
                DRAFT_KEY
            );


            syncInputsFromState();


            renderDays();


            renderFacilities();


            refs.save.textContent =
                "このプランを保存";


            closeModal(
                refs.draftModal
            );

        }



        /* =====================================================
           BOOT
        ====================================================== */

        function boot() {

            const params =
                new URLSearchParams(
                    location.search
                );


            const editId =
                params.get(
                    "edit"
                );


            /*
            保存済みプラン編集
            */

            if (
                editId
            ) {

                const plan =
                    readHistory()
                    .find(
                        function (
                            item
                        ) {

                            return (

                                item

                                &&

                                item.id
                                ===
                                editId

                                &&

                                item.planType
                                ===
                                "manual"

                            );

                        }
                    );


                if (
                    plan
                ) {

                    loadState(
                        plan
                    );


                    return;

                }

            }



            /*
            下書き
            */

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

                state =
                    clone(
                        draft.state
                    );


                syncInputsFromState();


                renderDays();


                renderFacilities();


                openModal(
                    refs.draftModal
                );

            }

            else {

                loadState(
                    createBlankState()
                );

            }

        }



        /* =====================================================
           EVENTS
        ====================================================== */

        refs.filterTabs.addEventListener(
            "click",
            function (
                event
            ) {

                const button =
                    event.target.closest(
                        "button[data-filter]"
                    );


                if (
                    !button
                ) {

                    return;

                }


                currentFilter =
                    button.dataset.filter;


                refs.filterTabs
                .querySelectorAll(
                    "button"
                )
                .forEach(
                    function (
                        item
                    ) {

                        item.classList.toggle(

                            "active",

                            item
                            ===
                            button

                        );

                    }
                );


                renderFacilities();

            }
        );



        refs.search.addEventListener(
            "input",
            renderFacilities
        );



        [

            refs.title,

            refs.date,

            refs.days,

            refs.people,

            refs.member,

            refs.car,

            refs.memo

        ]
        .forEach(
            function (
                element
            ) {

                element.addEventListener(
                    "change",
                    changed
                );


                element.addEventListener(
                    "input",
                    saveDraftDebounced
                );

            }
        );



        refs.save.addEventListener(
            "click",
            function () {

                savePlan(
                    false
                );

            }
        );



        refs.preview.addEventListener(
            "click",
            previewPlan
        );



        refs.clear.addEventListener(
            "click",
            function () {

                const confirmed =
                    confirm(
                        "DAYに追加した予定をすべて削除しますか？"
                    );


                if (
                    !confirmed
                ) {

                    return;

                }


                state.day1 =
                    [];


                state.day2 =
                    [];


                state.day3 =
                    [];


                changed();

            }
        );



        refs.detailClose.addEventListener(
            "click",
            function () {

                closeModal(
                    refs.detailModal
                );

            }
        );



        refs.detailModal.addEventListener(
            "click",
            function (
                event
            ) {

                if (
                    event.target
                    ===
                    refs.detailModal
                ) {

                    closeModal(
                        refs.detailModal
                    );

                }

            }
        );



        refs.continueDraft.addEventListener(
            "click",
            function () {

                closeModal(
                    refs.draftModal
                );


                loadState(
                    state
                );

            }
        );



        refs.newDraft.addEventListener(
            "click",
            function () {

                const confirmed =
                    confirm(
                        "作成途中の下書きを破棄して新しく作りますか？"
                    );


                if (
                    confirmed
                ) {

                    startNewPlan();

                }

            }
        );



        window.addEventListener(
            "storage",
            function (
                event
            ) {

                if (
                    event.key
                    ===
                    FAVORITES_KEY
                ) {

                    renderFacilities();

                }

            }
        );



        /* =====================================================
           START
        ====================================================== */

        boot();

    }
);