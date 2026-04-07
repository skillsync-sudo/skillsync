(function() {
    // --- 1. DATA ARRAYS ---
    const jobCategories = [
        "Software Engineering", "Marketing", "UI/UX Design", "Data Science",
        "Finance", "Healthcare", "Education", "Customer Support", "Sales", "Construction"
    ];

    const productList = [
        "Resume Builder", "Mock Interviews", "Skill Assessments", "Career Roadmap", 
        "Mentorship", "Portfolio Hosting", "Job Alerts", "Networking Hub"
    ];

    // --- 2. SELECTORS ---
    const jobContainer = document.getElementById('jobCategories');
    const jobBtn = document.getElementById('showMoreJobs');
    const productContainer = document.getElementById('productsContainer');
    const productBtn = document.getElementById('showMoreProducts');

    // --- 3. REUSABLE RENDER FUNCTION ---
    function renderList(data, container, limit) {
        if (!container) return; 
        container.innerHTML = ''; 
        
        const itemsToShow = data.slice(0, limit);
        
        itemsToShow.forEach(item => {
            const btn = document.createElement('button');
            // Keep your original styling
            btn.className = 'btn btn-outline-primary rounded-pill px-4 py-2';
            btn.textContent = item;
            
            // --- THE FIX: Direct Redirect ---
            // This replaces the old handleJobSelect/handleProductSelect calls
            btn.onclick = () => {
                // Since this is an external JS file, we use the hardcoded path.
                // Make sure your Flask route for registration is actually "/register"
                window.location.href = "/register"; 
            };
            
            container.appendChild(btn);
        });
    }

    // --- 4. EVENT LISTENERS ("Show More" Buttons) ---

    if (jobBtn) {
        jobBtn.addEventListener('click', () => {
            renderList(jobCategories, jobContainer, jobCategories.length);
            jobBtn.style.display = 'none'; // Hide button after expanding
        });
    }

    if (productBtn) {
        productBtn.addEventListener('click', () => {
            renderList(productList, productContainer, productList.length);
            productBtn.style.display = 'none'; // Hide button after expanding
        });
    }

    // --- 5. INITIAL LOAD ---
    renderList(jobCategories, jobContainer, 4);
    renderList(productList, productContainer, 4);

})(); // End of IIFE