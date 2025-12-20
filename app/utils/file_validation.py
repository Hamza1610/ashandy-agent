"""
File Upload Validation: Product image validation with AI-powered detection.

Validates: File type, size, actual image format, and product content
AWS EC2 Compatible: Uses existing Pillow and requests libraries
"""
import requests
from PIL import Image
from io import BytesIO
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Allowed image types
ALLOWED_MIME_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/jpg']
ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp']

# File size limits
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB (generous for product photos)
MIN_FILE_SIZE = 1024  # 1KB (avoid tiny tracking pixels)
RECOMMENDED_MAX_SIZE = 5 * 1024 * 1024  # 5MB (recommended)

# Dimension limits
MIN_DIMENSION = 50    # Minimum width/height (too small = suspicious)
MAX_DIMENSION = 5000  # Maximum width/height (giant images)
RECOMMENDED_MIN = 200  # Recommended minimum for product photos
RECOMMENDED_MAX = 2000  # Recommended maximum

# Product detection keywords (from visual analysis)
PRODUCT_INDICATORS = [
    # Containers
    'bottle', 'jar', 'container', 'box', 'tube', 'packaging', 'pump',
    # Cosmetic specific
    'cosmetic', 'skincare', 'makeup', 'beauty', 'serum', 'cream', 'lotion',
    'moisturizer', 'cleanser', 'toner', 'mask', 'sunscreen', 'foundation',
    # Brand/Product identifiers
    'label', 'brand', 'product', 'package', 'logo',
    # Colors that suggest products
    'bottles', 'containers', 'jars', 'tubes'
]


async def validate_image_url(
    url: str, 
    check_product: bool = True,
    strict: bool = False
) -> dict:
    """
    Comprehensive image validation from URL.
    
    Args:
        url: Image URL to validate
        check_product: If True, verify it's likely a product image using AI
        strict: If True, reject images that don't look like products
    
    Returns:
        {
            'valid': bool,
            'error': str or None,
            'warnings': list,
            'metadata': dict,
            'is_product': bool (if check_product=True)
        }
    
    Example:
        >>> result = await validate_image_url("https://example.com/product.jpg")
        >>> if result['valid']:
        ...     print(f"Image OK: {result['metadata']['dimensions']}")
    """
    result = {
        'valid': False,
        'error': None,
        'warnings': [],
        'metadata': {},
        'is_product': None
    }
    
    try:
        # Step 1: HEAD request to check size and type WITHOUT downloading
        logger.info(f"📐 Validating image: {url[:50]}...")
        head_response = requests.head(url, timeout=5, allow_redirects=True)
        
        content_type = head_response.headers.get('Content-Type', '').lower()
        content_length = int(head_response.headers.get('Content-Length', 0))
        
        # Validate MIME type
        if content_type and content_type not in ALLOWED_MIME_TYPES:
            result['error'] = f"Invalid file type: {content_type}. Only JPEG, PNG, WebP allowed."
            logger.warning(f"❌ {result['error']}")
            return result
        
        # Validate size (if available in headers)
        if content_length > 0:
            if content_length > MAX_FILE_SIZE:
                result['error'] = f"File too large: {content_length / 1024 / 1024:.1f}MB (max {MAX_FILE_SIZE / 1024 / 1024}MB)"
                logger.warning(f"❌ {result['error']}")
                return result
            
            if content_length < MIN_FILE_SIZE:
                result['error'] = f"File too small: {content_length} bytes (min {MIN_FILE_SIZE})"
                logger.warning(f"❌ {result['error']}")
                return result
            
            if content_length > RECOMMENDED_MAX_SIZE:
                result['warnings'].append(
                    f"Large file ({content_length / 1024 / 1024:.1f}MB). Consider compressing for faster uploads."
                )
        
        # Step 2: Download and validate actual image
        logger.info(f"⬇️ Downloading image for validation...")
        response = requests.get(url, timeout=15)  # Longer timeout for large images
        response.raise_for_status()
        
        actual_size = len(response.content)
        
        # Double-check size after download
        if actual_size > MAX_FILE_SIZE:
            result['error'] = f"Downloaded file too large: {actual_size / 1024 / 1024:.1f}MB"
            return result
        
        # Verify it's actually a valid image
        try:
            img = Image.open(BytesIO(response.content))
            img.verify()  # Verify image integrity
            
            # Re-open for dimension check (verify() can't be followed by other operations)
            img = Image.open(BytesIO(response.content))
            
        except Exception as e:
            result['error'] = f"Invalid or corrupted image: {str(e)}"
            logger.warning(f"❌ {result['error']}")
            return result
        
        # Check dimensions
        width, height = img.size
        
        if width < MIN_DIMENSION or height < MIN_DIMENSION:
            result['error'] = f"Image too small: {width}x{height} (min {MIN_DIMENSION}x{MIN_DIMENSION})"
            return result
        
        if width > MAX_DIMENSION or height > MAX_DIMENSION:
            result['error'] = f"Image too large: {width}x{height} (max {MAX_DIMENSION}x{MAX_DIMENSION})"
            return result
        
        # Warnings for non-ideal dimensions
        if width < RECOMMENDED_MIN or height < RECOMMENDED_MIN:
            result['warnings'].append(
                f"Image quite small ({width}x{height}). Product photos work best at {RECOMMENDED_MIN}x{RECOMMENDED_MIN} or larger."
            )
        
        if width > RECOMMENDED_MAX or height > RECOMMENDED_MAX:
            result['warnings'].append(
                f"Very large image ({width}x{height}). Will be slow to process. Consider resizing."
            )
        
        # Store metadata
        result['metadata'] = {
            'format': img.format,
            'mode': img.mode,  # RGB, RGBA, etc.
            'size_bytes': actual_size,
            'size_mb': round(actual_size / 1024 / 1024, 2),
            'dimensions': f"{width}x{height}",
            'width': width,
            'height': height,
            'mime_type': content_type or f"image/{img.format.lower()}"
        }
        
        logger.info(f"✅ Image valid: {img.format} {width}x{height} ({actual_size / 1024:.0f}KB)")
        
        # Step 3: Product Detection (if requested)
        if check_product:
            logger.info(f"🔍 Checking if image contains product...")
            
            try:
                # Use existing visual analysis infrastructure
                from app.tools.visual_tools import detect_product_from_image
                
                detection = await detect_product_from_image.ainvoke(url)
                
                if detection and not detection.get('error'):
                    detected_text = (detection.get('detected_text', '') or '').lower()
                    product_type = (detection.get('product_type', '') or '').lower()
                    visual_desc = (detection.get('visual_description', '') or '').lower()
                    confidence = detection.get('confidence', 0)
                    
                    # Check if it looks like a product
                    is_product = any(
                        indicator in detected_text or 
                        indicator in product_type or 
                        indicator in visual_desc
                        for indicator in PRODUCT_INDICATORS
                    )
                    
                    result['is_product'] = is_product
                    result['metadata']['product_detection'] = {
                        'detected_text': detected_text,
                        'product_type': product_type,
                        'visual_description': visual_desc,
                        'confidence': confidence,
                        'is_product': is_product
                    }
                    
                    # Warnings/errors based on detection
                    if not is_product and confidence > 0.6:
                        warning = (
                            "⚠️ This doesn't appear to be a product image. "
                            "Please upload photos of cosmetic/skincare products only. "
                            f"Detected: {product_type or visual_desc or 'non-product content'}"
                        )
                        result['warnings'].append(warning)
                        logger.warning(warning)
                        
                        # Strict mode: Reject non-products
                        if strict:
                            result['error'] = "Image must be a cosmetic/skincare product photo"
                            result['valid'] = False
                            return result
                    elif is_product:
                        logger.info(f"✅ Product detected: {product_type or detected_text}")
                else:
                    result['warnings'].append("Product verification unavailable (AI analysis failed)")
                    logger.warning("⚠️ Product detection failed, allowing image")
            
            except Exception as e:
                logger.error(f"Product detection error: {e}", exc_info=True)
                result['warnings'].append("Could not verify product content (analysis error)")
        
        # All checks passed
        result['valid'] = True
        return result
        
    except requests.Timeout:
        result['error'] = "Image download timeout (server too slow or file too large)"
        logger.error(f"❌ {result['error']}")
        return result
    
    except requests.RequestException as e:
        result['error'] = f"Network error downloading image: {str(e)}"
        logger.error(f"❌ {result['error']}")
        return result
    
    except Exception as e:
        result['error'] = f"Image validation error: {str(e)}"
        logger.error(f"❌ {result['error']}: {e}", exc_info=True)
        return result


def validate_image_extension(filename: str) -> bool:
    """
    Quick check if filename has valid image extension.
    
    Args:
        filename: File name or path
    
    Returns:
        True if valid extension
    """
    if not filename:
        return False
    
    filename_lower = filename.lower()
    return any(filename_lower.endswith(ext) for ext in ALLOWED_EXTENSIONS)


async def validate_and_log_image(url: str, user_id: str = "unknown") -> tuple[bool, Optional[str]]:
    """
    Validate image and log result (convenience function for webhooks).
    
    Args:
        url: Image URL
        user_id: User identifier for logging
    
    Returns:
        (is_valid, error_message)
        If valid: (True, None)
        If invalid: (False, "Error message")
    """
    result = await validate_image_url(url, check_product=True, strict=False)
    
    if not result['valid']:
        logger.warning(f"🚫 Image validation failed for {user_id}: {result['error']}")
        return False, result['error']
    
    if result['warnings']:
        logger.info(f"⚠️ Image warnings for {user_id}: {', '.join(result['warnings'])}")
    
    if result.get('is_product') is False:
        logger.warning(f"⚠️ Non-product image from {user_id}, but allowing")
    
    return True, None
