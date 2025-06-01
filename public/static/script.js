document.addEventListener('DOMContentLoaded', function() {
    const input = document.getElementById('productImage');
    const preview = document.getElementById('imagePreview');
    const searchInput = document.getElementById('productSearch');
    const autocompleteList = document.getElementById('autocompleteList');
    const resultDiv = document.getElementById('result');
    const photoButton = document.getElementById('photoButton');
    const searchButton = document.getElementById('searchButton');
    const photoSection = document.getElementById('photoSection');
    const searchSection = document.getElementById('searchSection');
    const photoWarning = document.getElementById('photoWarning');

    if (photoButton && searchButton && photoSection && searchSection && photoWarning) {
        window.switchToPhoto = function() {
            photoButton.classList.add('active');
            searchButton.classList.remove('active');
            photoSection.style.display = 'block';
            searchSection.style.display = 'none';
            photoWarning.style.display = 'block';
            resultDiv.innerHTML = '';
            searchInput.value = '';
            autocompleteList.innerHTML = '';
            preview.innerHTML = '';
        };

        window.switchToSearch = function() {
            searchButton.classList.add('active');
            photoButton.classList.remove('active');
            searchSection.style.display = 'block';
            photoSection.style.display = 'none';
            photoWarning.style.display = 'none';
            resultDiv.innerHTML = '';
            preview.innerHTML = '';
            input.value = '';
        };
    }

    if (input && preview) {
        input.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(event) {
                    preview.innerHTML = `<img src="${event.target.result}" alt="Uploaded Image" class="preview-image">`;
                };
                reader.readAsDataURL(file);
            }
        });
    }

    window.processImage = async function() {
        if (!resultDiv || !input) return;
        resultDiv.innerHTML = '<div class="spinner"></div>جاري معالجة الصورة...';
        if (!input.files || !input.files[0]) {
            resultDiv.innerHTML = 'يرجى تحميل صورة أولاً.';
            return;
        }

        const file = input.files[0];
        const formData = new FormData();
        formData.append('image', file);

        try {
            const response = await fetch('/api/process_image', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error('خطأ في الاتصال بالخادم');
            }

            const data = await response.json();
            console.log('Full response (processImage):', data);
            if (data.error || !data.detected_product) {
                resultDiv.innerHTML = 'لم يتم التعرف على المنتج. يرجى الذهاب إلى صفحة الإبلاغ لإضافته.';
                return;
            }

            resultDiv.innerHTML = `✅ تم التعرف على المنتج: ${data.detected_product}`;
            const boycotted = data.is_boycotted !== undefined ? Boolean(data.is_boycotted) : false;
            console.log('Processed boycotted value (processImage):', boycotted);
            const statusText = boycotted ? 'مقاطعه' : 'غير مقاطعه';
            const statusClass = boycotted ? 'boycotted' : 'non-boycotted';
            resultDiv.innerHTML += `<span class="status-circle ${statusClass}">${statusText}</span>`;
            if (data.alternatives && data.alternatives.length > 0) {
                let html = '<h3>🟢 البدائل المقترحة:</h3><ul>';
                data.alternatives.forEach(alt => {
                    html += `<li>${alt.name}</li>`;
                });
                html += '</ul>';
                resultDiv.innerHTML += html;
            }
        } catch (error) {
            resultDiv.innerHTML = `خطأ: ${error.message}`;
        }
    };

    async function fetchSuggestions(query) {
        try {
            const response = await fetch(`/api/search_products?query=${encodeURIComponent(query)}`);
            if (!response.ok) {
                throw new Error('خطأ في جلب الاقتراحات');
            }
            const data = await response.json();
            return data.products;
        } catch (error) {
            console.error('Error fetching suggestions:', error);
            return [];
        }
    }

    if (searchInput && autocompleteList) {
        searchInput.addEventListener('input', async function(e) {
            const query = e.target.value.trim();
            autocompleteList.innerHTML = '';
            if (query.length < 2) return;

            const products = await fetchSuggestions(query);
            if (products.length === 0) {
                autocompleteList.innerHTML = '<div class="autocomplete-item">لا توجد نتائج</div>';
                return;
            }

            products.forEach(product => {
                const item = document.createElement('div');
                item.classList.add('autocomplete-item');
                item.textContent = product.name;
                item.addEventListener('click', () => {
                    searchInput.value = product.name;
                    autocompleteList.innerHTML = '';
                    searchProduct(product.product_id);
                });
                autocompleteList.appendChild(item);
            });
        });
    }

    async function searchProduct(productId) {
        if (!resultDiv) return;
        resultDiv.innerHTML = '<div class="spinner"></div>جاري البحث عن المنتج...';
        try {
            const response = await fetch(`/api/search_products?query=${encodeURIComponent(searchInput.value)}`);
            if (!response.ok) {
                throw new Error('خطأ في الاتصال بالخادم');
            }

            const data = await response.json();
            if (data.error || !data.products.find(p => p.product_id === productId)) {
                resultDiv.innerHTML = 'لم يتم العثور على المنتج. يرجى الذهاب إلى صفحة الإبلاغ لإضافته.';
                return;
            }

            const product = data.products.find(p => p.product_id === productId);

            try {
                const simResponse = await fetch('/api/process_image', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: product.name })
                });

                if (!simResponse.ok) {
                    throw new Error('خطأ في جلب البدائل');
                }

                const simData = await simResponse.json();
                console.log('Full response (searchProduct):', simData);
                if (simData.error || !simData.detected_product) {
                    resultDiv.innerHTML = 'لم يتم التعرف على المنتج. يرجى الذهاب إلى صفحة الإبلاغ لإضافته.';
                    return;
                }

                resultDiv.innerHTML = `✅ المنتج: ${product.name}`;
                const boycotted = simData.is_boycotted !== undefined ? Boolean(simData.is_boycotted) : false;
                console.log('Processed boycotted value (searchProduct):', boycotted);
                const statusText = boycotted ? 'مقاطعه' : 'غير مقاطعه';
                const statusClass = boycotted ? 'boycotted' : 'non-boycotted';
                resultDiv.innerHTML += `<span class="status-circle ${statusClass}">${statusText}</span>`;
                if (simData.alternatives && simData.alternatives.length > 0) {
                    let html = '<h3>🟢 البدائل المقترحة:</h3><ul>';
                    simData.alternatives.forEach(alt => {
                        html += `<li>${alt.name}</li>`;
                    });
                    html += '</ul>';
                    resultDiv.innerHTML += html;
                }
            } catch (error) {
                resultDiv.innerHTML += `<p>خطأ في جلب البدائل: ${error.message}</p>`;
            }
        } catch (error) {
            resultDiv.innerHTML = `خطأ: ${error.message}`;
        }
    }

    const arrowNavLinks = document.querySelectorAll('.arrow-nav a');
    if (arrowNavLinks.length > 0) {
        arrowNavLinks.forEach(link => {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                const href = this.getAttribute('href');
                const currentUrl = window.location.pathname.replace(/^\/|\/$/g, '');
                const targetPath = href.replace(/^\/|\/$/g, '');

                console.log('Navigating from:', currentUrl, 'to:', href);

                if (href) {
                    const overlay = document.createElement('div');
                    overlay.classList.add('overlay');
                    const redExpand = document.createElement('div');
                    redExpand.classList.add('red-expand');
                    const message = document.createElement('div');
                    message.classList.add('overlay-message');
                    message.textContent = 'قاطع لسا القضيه مخلصتش 😢';
                    overlay.appendChild(message);
                    document.body.appendChild(overlay);
                    document.body.appendChild(redExpand);

                    setTimeout(() => {
                        overlay.classList.add('active');
                        redExpand.classList.add('expand');
                    }, 50);

                    setTimeout(() => {
                        window.location.href = href;
                    }, 1500);

                    setTimeout(() => {
                        message.classList.add('fade-out');
                        setTimeout(() => {
                            overlay.classList.add('slide-right');
                            redExpand.classList.add('fly');
                            setTimeout(() => {
                                overlay.remove();
                                redExpand.remove();
                            }, 500);
                        }, 1000);
                    }, 3000);
                } else {
                    console.error('Invalid href:', href);
                }
            });
        });
    }
});