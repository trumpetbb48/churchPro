let songs = [];
let showingFavorites = false;

// 1. FETCH: This pulls the data from your Flask /lyrics route
function loadSongs() {
    fetch("/lyrics")
        .then(res => res.json())
        .then(data => {
            songs = data;
            renderSongs(songs);
        })
        .catch(err => console.error("Error loading songs:", err));
}

// 2. RENDER: This turns the JSON data into HTML list items
function renderSongs(list) {
    const container = document.getElementById("songs");
    if (!container) return; // Safety check
    
    container.innerHTML = "";

    list.forEach((song) => {
        const li = document.createElement("li");
        li.className = "menu-item"; // Reusing your CSS for the box look
        li.style.display = "flex";
        li.style.justifyContent = "space-between";
        li.style.alignItems = "center";
        li.style.marginBottom = "10px";
        li.style.cursor = "pointer";

        const titleSpan = document.createElement("span");
        titleSpan.className = "song-title";
        titleSpan.style.fontWeight = "bold";
        titleSpan.textContent = song.title; // textContent, not innerHTML: song titles are user-submitted

        const favSpan = document.createElement("span");
        favSpan.className = "fav-btn";
        favSpan.style.fontSize = "1.5em";
        favSpan.style.color = "#d4af37";
        favSpan.textContent = song.favorite ? "★" : "☆";

        li.appendChild(titleSpan);
        li.appendChild(favSpan);

        // Action: Click the song to open details
        li.addEventListener("click", (e) => {
            // Prevent opening the song if the user only clicked the Star
            if (e.target.classList.contains("fav-btn")) return;
            // Link by title, not list position — position shifts when filtering
            // to Favorites or reordering, which used to open the wrong song.
            window.location.href = "/song/" + encodeURIComponent(song.title);
        });

        // Action: Click the star to favorite
        li.querySelector(".fav-btn").addEventListener("click", (e) => {
            e.stopPropagation();
            toggleFavorite(song);
        });

        container.appendChild(li);
    });
}

// 3. FAVORITE: This updates the "star" status on the server
function toggleFavorite(song) {
    fetch("/favorite", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: song.title })
    })
    .then(() => {
        song.favorite = !song.favorite;
        // Re-draw the list to show the new star
        renderSongs(showingFavorites ? songs.filter(s => s.favorite) : songs);
    });
}

// 4. FILTERS: Functions for the "All" and "Favorites" buttons
function showFavorites() {
    showingFavorites = true;
    renderSongs(songs.filter(s => s.favorite));
}

function showAll() {
    showingFavorites = false;
    renderSongs(songs);
}

// Start the process when the page loads
loadSongs();