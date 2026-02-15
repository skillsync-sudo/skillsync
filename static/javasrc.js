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
        if (!container) return; // Guard: Exit if container doesn't exist on this page
        container.innerHTML = ''; 
        
        const itemsToShow = data.slice(0, limit);
        
        itemsToShow.forEach(item => {
            const btn = document.createElement('button');
            btn.className = 'btn btn-outline-primary rounded-pill px-4 py-2';
            btn.textContent = item;
            
            btn.onclick = () => {
                if (container.id === 'jobCategories') {
                    handleJobSelect(item);
                } else {
                    handleProductSelect();
                }
            };
            container.appendChild(btn);
        });
    }

    // --- 4. EVENT LISTENERS (With Null Guards) ---

    // Safety check for Job Button
    if (jobBtn) {
        jobBtn.addEventListener('click', () => {
            renderList(jobCategories, jobContainer, jobCategories.length);
            jobBtn.style.display = 'none';
        });
    }

    // Safety check for Product Button
    if (productBtn) {
        productBtn.addEventListener('click', () => {
            renderList(productList, productContainer, productList.length);
            productBtn.style.display = 'none';
        });
    }

    // --- 5. FEEDBACK LOGIC ---

    function handleJobSelect(name) {
        const feedback = document.getElementById('selectedCategoryFeedback');
        const nameDisplay = document.getElementById('selectedCategoryName');
        if (feedback && nameDisplay) {
            nameDisplay.textContent = name;
            feedback.classList.remove('d-none');
        }
    }

    let selectedCount = 0;
    function handleProductSelect() {
        selectedCount++;
        const summary = document.getElementById('selectedProductsSummary');
        const countDisplay = document.getElementById('selectedProductsCount');
        if (summary && countDisplay) {
            countDisplay.textContent = selectedCount;
            summary.classList.remove('d-none');
        }
    }

    // --- 6. INITIAL LOAD ---
    // These functions now safely check if containers exist before running
    renderList(jobCategories, jobContainer, 4);
    renderList(productList, productContainer, 4);

})(); // End of IIFE