#!/bin/bash
# Script to push code to GitHub after repository is created

cd "/Users/htargett/Desktop/Territory Planning Research APp"

echo "=== Pushing Territory Planner to GitHub ==="
echo ""
echo "Please ensure you have created the repository at:"
echo "https://github.com/htargett/territory-planning-research"
echo ""
read -p "Have you created the repository? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Pushing to GitHub..."
    git push -u origin main
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "✅ Success! Your code is now on GitHub"
        echo ""
        echo "Repository: https://github.com/htargett/territory-planning-research"
        echo ""
        echo "Next steps:"
        echo "1. View your repo: https://github.com/htargett/territory-planning-research"
        echo "2. Update server deployment (see GITHUB_SETUP.md)"
        echo "3. Follow CLEANUP_PLAN.md to mount persistent disk"
    else
        echo ""
        echo "❌ Push failed. Check your GitHub authentication."
        echo ""
        echo "Troubleshooting:"
        echo "- Make sure the repository exists: https://github.com/htargett/territory-planning-research"
        echo "- Check SSH key is added to GitHub: https://github.com/settings/keys"
        echo "- Test SSH: ssh -T git@github.com"
    fi
else
    echo ""
    echo "Please create the repository first at:"
    echo "https://github.com/new?name=territory-planning-research"
    echo ""
    echo "Then run this script again."
fi
